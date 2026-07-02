from __future__ import annotations

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import app_store
from .retrieval import search_retrieval
from .retrieval.merge import normalized_title
from .retrieval.providers import ai_pixel_chat_json, default_provider_registry, retrieval_model_status, use_ai_pixel_config


_ACTIVE_SEARCH_WORKERS: set[str] = set()
_ACTIVE_SEARCH_WORKERS_LOCK = threading.Lock()
_SEARCH_MODE_VALUES = {"topic", "natural", "agent"}
_MAX_SEARCH_EVENT_MESSAGE_LEN = 220
_MAX_SEARCH_EVENTS_PER_RUN = 30
_API_CONFIG_PREFERENCE_KEY = "api_config"


def normalize_search_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in _SEARCH_MODE_VALUES else "topic"


def search_mode_label(mode: str) -> str:
    return {"topic": "主题词检索", "natural": "自然语言检索", "agent": "智能体检索"}.get(mode, "主题词检索")


def _clean_secret(value: Any) -> str:
    return str(value or "").strip()


def _api_config_for_library(library_id: str) -> dict[str, Any]:
    value = app_store.get_preference(library_id, _API_CONFIG_PREFERENCE_KEY, {})
    return value if isinstance(value, dict) else {}


def _api_config_model_for_library(library_id: str) -> dict[str, str]:
    config = _api_config_for_library(library_id)
    model = config.get("model") if isinstance(config.get("model"), dict) else {}
    return {
        "model": _clean_secret(model.get("model") or model.get("model_name")),
        "base_url": _clean_secret(model.get("base_url") or model.get("request_url") or model.get("url")),
        "api_key": _clean_secret(model.get("api_key") or model.get("key")),
    }


def _api_config_tokens_for_library(library_id: str) -> dict[str, str]:
    config = _api_config_for_library(library_id)
    code_sources = config.get("code_sources") if isinstance(config.get("code_sources"), dict) else {}
    return {
        "github_token": _clean_secret(code_sources.get("github_token") or code_sources.get("github")),
        "huggingface_token": _clean_secret(code_sources.get("huggingface_token") or code_sources.get("huggingface")),
        "zenodo_token": _clean_secret(code_sources.get("zenodo_token") or code_sources.get("zenodo")),
    }


def _effective_code_source_token(library_id: str, key: str, env_name: str) -> str:
    configured = _api_config_tokens_for_library(library_id).get(key, "")
    return configured or _clean_secret(os.environ.get(env_name))


def _retrieval_provider_registry_for_library(library_id: str) -> dict[str, Any]:
    local_config = app_store.retrieval_local_config(library_id) or {}
    return default_provider_registry(
        local_file_paths=local_config.get("paths") if isinstance(local_config.get("paths"), list) else None,
        local_file_field_map=local_config.get("field_map") if isinstance(local_config.get("field_map"), dict) else {},
        http_json_config_value=app_store.retrieval_http_json_config(library_id),
        sqlite_config_value=app_store.retrieval_sqlite_config(library_id),
        manifest_config_value=app_store.retrieval_manifest_config(library_id),
        github_token=_effective_code_source_token(library_id, "github_token", "GITHUB_TOKEN"),
        huggingface_token=_effective_code_source_token(library_id, "huggingface_token", "HUGGINGFACE_TOKEN"),
        zenodo_token=_effective_code_source_token(library_id, "zenodo_token", "ZENODO_ACCESS_TOKEN"),
    )


def _clean_event_message(message: str) -> str:
    return " ".join(str(message or "").split())[:_MAX_SEARCH_EVENT_MESSAGE_LEN].strip()


def _append_run_event(library_id: str, search_run_id: str, message: str, kind: str = "progress") -> None:
    cleaned = _clean_event_message(message)
    if not cleaned:
        return
    recent_events = app_store.list_search_run_events(library_id, search_run_id, limit=1)
    if recent_events:
        latest = recent_events[-1]
        if str(latest.get("message") or "") == cleaned and str(latest.get("kind") or "") == kind:
            return
    app_store.append_search_run_event(library_id, search_run_id, message=cleaned, kind=kind)


def _trim_run_events(library_id: str, search_run_id: str) -> None:
    events = app_store.list_search_run_events(library_id, search_run_id, limit=_MAX_SEARCH_EVENTS_PER_RUN + 12)
    if len(events) <= _MAX_SEARCH_EVENTS_PER_RUN:
        return
    overflow = events[:-_MAX_SEARCH_EVENTS_PER_RUN]
    with app_store.connect() as conn:
        for item in overflow:
            conn.execute(
                "DELETE FROM search_run_events WHERE library_id = ? AND search_run_id = ? AND event_id = ?",
                (library_id, search_run_id, str(item.get("event_id") or "")),
            )
        conn.commit()


def _run_status(library_id: str, search_run_id: str) -> str:
    run = app_store.get_search_run(library_id, search_run_id)
    return str(run.get("status") or "") if run else ""


def _run_is_terminal(status: str) -> bool:
    return status in {"success", "failed", "stopped", "cancelled"}


def _source_summary_line(source: str, stats: dict[str, Any]) -> tuple[str, str]:
    elapsed_ms = int(stats.get("elapsed_ms") or 0)
    if stats.get("ok") is False:
        kind = str(stats.get("error_kind") or "error")
        return (f"{source} · {kind} · {elapsed_ms}ms", "warn")
    count = int(stats.get("count") or 0)
    return (f"{source} · {count} 条 · {elapsed_ms}ms", "progress")


def _retrieval_payload_to_search_candidates(payload: dict[str, Any], *, source_mode: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in payload.get("candidates") or []:
        candidate = dict(item) if isinstance(item, dict) else {}
        fields = candidate.get("item", {}).get("fields") if isinstance(candidate.get("item"), dict) else {}
        title = str(candidate.get("title") or fields.get("title") or "").strip()
        if not title:
            continue
        authors = []
        creators = candidate.get("creators") if isinstance(candidate.get("creators"), list) else candidate.get("item", {}).get("creators", [])
        for creator in creators or []:
            if not isinstance(creator, dict):
                continue
            name = str(
                creator.get("name")
                or " ".join(str(creator.get(key) or "").strip() for key in ("first_name", "last_name", "firstName", "lastName")).strip()
            ).strip()
            if name:
                authors.append(name)
        identifiers = candidate.get("identifiers") if isinstance(candidate.get("identifiers"), dict) else {}
        keywords = candidate.get("keywords") if isinstance(candidate.get("keywords"), list) else []
        year = str(candidate.get("year") or fields.get("date") or "").strip()
        if len(year) >= 4:
            year = year[:4]
        values.append(
            {
                "title": title,
                "normalized_title": normalized_title(title),
                "authors": authors,
                "year": year,
                "venue": str(candidate.get("venue") or fields.get("publicationTitle") or "").strip(),
                "doi": str(identifiers.get("doi") or candidate.get("doi") or fields.get("DOI") or "").strip(),
                "paper_url": str(candidate.get("landing_url") or candidate.get("paper_url") or fields.get("url") or "").strip(),
                "pdf_url": str(candidate.get("pdf_url") or "").strip(),
                "abstract": str(candidate.get("abstract") or fields.get("abstractNote") or "").strip(),
                "abstract_zh": str(candidate.get("abstract_zh") or "").strip(),
                "keywords": [str(keyword).strip() for keyword in keywords if str(keyword).strip()],
                "item_type": str(candidate.get("item_type") or candidate.get("item", {}).get("item_type") or "").strip(),
                "source": str(candidate.get("source") or "").strip(),
                "source_mode": source_mode,
            }
        )
    return values


def _sync_candidate_merge(library_id: str, search_run_id: str, raw_results: list[dict[str, Any]]) -> dict[str, Any]:
    merge = app_store.upsert_search_candidates(library_id, search_run_id, raw_results)
    candidate_count = len(app_store.list_search_candidates(library_id))
    app_store.update_search_run(
        search_run_id,
        candidate_count=candidate_count,
        inserted_count=int(merge.get("inserted_count") or 0),
        deduped_count=int(merge.get("deduped_count") or 0),
        updated_count=max(0, len(raw_results) - int(merge.get("inserted_count") or 0)),
    )
    return merge


def _search_compile_messages(user_request: str, source_names: list[str]) -> list[dict[str, str]]:
    source_text = ", ".join(source_names) if source_names else "crossref, arxiv, pubmed, semanticscholar, datacite"
    schema = {
        "normalized_request": "归一化后的检索任务描述",
        "must_terms": ["必须保留的术语"],
        "preferred_terms": ["偏好术语"],
        "excluded_terms": ["排除术语"],
        "queries": [
            {
                "query": "检索词",
                "intent": "core_topic | method | benchmark | survey",
                "language": "zh | en",
                "source_groups": ["crossref", "arxiv"],
            }
        ],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是科研检索 query compiler。任务是把自然语言检索需求编译为多源检索 queries。"
                "必须照顾中文输入：英文论文源要生成英文 query，中文源可生成中文 query。"
                "要主动补齐翻译、别名、上下义词、任务拆分词，而不是只在原词后加固定英文后缀。"
                "不要把平台名写进对应平台 query：GitHub query 不要包含 GitHub，HuggingFace query 不要包含 HuggingFace，Zenodo query 不要包含 Zenodo。"
                "github、huggingface、zenodo 的 query 使用空格分隔关键词，不要使用 OR、AND、括号或复杂布尔语法。"
                "crossref、arxiv、pubmed、semanticscholar、datacite 可以使用短语和布尔词，但必须保持简短可执行。"
                "只能返回严格 JSON，不要输出任何额外说明。"
                "queries 至少 3 条，至多 8 条；每条必须包含 query、intent、language、source_groups。"
                f"本轮可用源：{source_text}。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"user_request": user_request, "source_names": source_names, "schema": schema}, ensure_ascii=False),
        },
    ]


SIMPLE_KEYWORD_SOURCES = {"github", "huggingface", "zenodo"}


def _simple_keyword_query(query: str) -> str:
    value = re.sub(r"\b(?:OR|AND|GitHub|HuggingFace|Zenodo)\b", " ", query, flags=re.IGNORECASE)
    value = re.sub(r"[()\"']", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compile_search_queries(library_id: str, user_request: str, source_names: list[str]) -> dict[str, Any]:
    clean_request = str(user_request or "").strip()
    if not clean_request:
        raise ValueError("检索描述不能为空。")
    with use_ai_pixel_config(_api_config_model_for_library(library_id)):
        model_status = retrieval_model_status()
        if not model_status.get("configured"):
            raise ValueError("模型未配置，请先前往 API 配置。")
        compiled = ai_pixel_chat_json(_search_compile_messages(clean_request, source_names), max_tokens=1200, timeout_seconds=90)
    queries = compiled.get("queries") if isinstance(compiled.get("queries"), list) else []
    normalized_queries: list[dict[str, Any]] = []
    for item in queries:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        groups = [str(group or "").strip().lower() for group in item.get("source_groups") or [] if str(group or "").strip()]
        if groups and set(groups).issubset(SIMPLE_KEYWORD_SOURCES):
            query = _simple_keyword_query(query)
        if not query or not groups:
            continue
        normalized_queries.append(
            {
                "query": query,
                "intent": str(item.get("intent") or "core_topic").strip() or "core_topic",
                "language": str(item.get("language") or "en").strip() or "en",
                "source_groups": groups,
            }
        )
    if not normalized_queries:
        raise ValueError("AI 未返回可用的检索词，请调整描述后重试。")
    return {
        "normalized_request": str(compiled.get("normalized_request") or clean_request).strip(),
        "must_terms": [str(item).strip() for item in compiled.get("must_terms") or [] if str(item).strip()],
        "preferred_terms": [str(item).strip() for item in compiled.get("preferred_terms") or [] if str(item).strip()],
        "excluded_terms": [str(item).strip() for item in compiled.get("excluded_terms") or [] if str(item).strip()],
        "queries": normalized_queries,
    }


def _run_topic_search(library_id: str, search_run_id: str, user_request: str, source_names: list[str]) -> tuple[list[dict[str, Any]], str]:
    payload = search_retrieval(
        user_request,
        sources=source_names,
        limit=5,
        include_raw=False,
        registry=_retrieval_provider_registry_for_library(library_id),
    )
    message_lines: list[str] = []
    for source_name, stats in (payload.get("source_stats") or {}).items():
        line, kind = _source_summary_line(str(source_name), stats if isinstance(stats, dict) else {})
        message_lines.append(line)
        _append_run_event(library_id, search_run_id, line, kind)
    candidates = _retrieval_payload_to_search_candidates(payload, source_mode="topic")
    merge = _sync_candidate_merge(library_id, search_run_id, candidates)
    pool_count = len(app_store.list_search_candidates(library_id))
    summary = f"去重后新增 {merge.get('inserted_count', 0)} 条，候选池共 {pool_count} 条。"
    _append_run_event(library_id, search_run_id, summary, "success")
    message_lines.append(summary)
    return candidates, "\n".join(message_lines)


def _run_natural_search(
    library_id: str,
    search_run_id: str,
    user_request: str,
    queries: list[dict[str, Any]],
    source_names: list[str],
) -> tuple[list[dict[str, Any]], str]:
    _append_run_event(library_id, search_run_id, "AI 编译已确认，开始按源执行检索。")
    message_lines: list[str] = ["AI 编译已确认，开始按源执行检索。"]
    by_source: dict[str, list[str]] = {}
    for item in queries:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        groups = [str(group or "").strip().lower() for group in item.get("source_groups") or [] if str(group or "").strip()]
        for group in groups:
            if source_names and group not in source_names:
                continue
            by_source.setdefault(group, []).append(query)
    if not by_source:
        raise ValueError("没有可执行的按源检索词。")

    def run_source(source_name: str, query_list: list[str]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        seen: set[str] = set()
        source_candidates: list[dict[str, Any]] = []
        total_count = 0
        elapsed_ms = 0
        error_kind = ""
        ok = True
        for query in query_list:
            if _run_status(library_id, search_run_id) == "cancelled":
                break
            clean_query = query.casefold()
            if clean_query in seen:
                continue
            seen.add(clean_query)
            payload = search_retrieval(
                query,
                sources=[source_name],
                limit=5,
                include_raw=False,
                registry=_retrieval_provider_registry_for_library(library_id),
            )
            stats = (payload.get("source_stats") or {}).get(source_name) if isinstance(payload.get("source_stats"), dict) else {}
            stat = stats if isinstance(stats, dict) else {}
            elapsed_ms += int(stat.get("elapsed_ms") or 0)
            if stat.get("ok") is False:
                ok = False
                error_kind = str(stat.get("error_kind") or "error")
                continue
            total_count += int(stat.get("count") or 0)
            source_candidates.extend(_retrieval_payload_to_search_candidates(payload, source_mode="natural"))
        return source_name, {"ok": ok, "count": total_count, "elapsed_ms": elapsed_ms, "error_kind": error_kind}, source_candidates

    merged_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(by_source))) as executor:
        futures = [executor.submit(run_source, source_name, query_list) for source_name, query_list in by_source.items()]
        for future in as_completed(futures):
            source_name, stats, source_candidates = future.result()
            line, kind = _source_summary_line(source_name, stats)
            message_lines.append(line)
            _append_run_event(library_id, search_run_id, line, kind)
            merged_results.extend(source_candidates)
    merge = _sync_candidate_merge(library_id, search_run_id, merged_results)
    pool_count = len(app_store.list_search_candidates(library_id))
    summary = f"去重后新增 {merge.get('inserted_count', 0)} 条，候选池共 {pool_count} 条。"
    _append_run_event(library_id, search_run_id, summary, "success")
    message_lines.append(summary)
    return merged_results, "\n".join(message_lines)


def _save_run_results(search_run_id: str, run: dict[str, Any], raw_results: list[dict[str, Any]], status: str) -> None:
    raw_result_path = Path(str(run.get("raw_result_path") or ""))
    raw_result_path.parent.mkdir(parents=True, exist_ok=True)
    raw_result_path.write_text(
        json.dumps(
            {
                "search_run_id": run.get("search_run_id"),
                "library_id": run.get("library_id"),
                "mode": run.get("mode"),
                "user_request": run.get("user_request"),
                "status": status,
                "results": raw_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _execute_search_run(
    library_id: str,
    search_run_id: str,
    *,
    mode: str,
    user_request: str,
    source_names: list[str],
    compiled_queries: list[dict[str, Any]] | None = None,
) -> None:
    run = app_store.get_search_run(library_id, search_run_id)
    if not run:
        return
    try:
        app_store.update_search_run(search_run_id, status="running")
        _append_run_event(library_id, search_run_id, f"已启动{search_mode_label(mode)}。")
        if mode == "agent":
            raise ValueError("智能体检索将在第二阶段接入。")
        if mode == "natural":
            raw_results, assistant_message = _run_natural_search(
                library_id,
                search_run_id,
                user_request,
                compiled_queries or [],
                source_names,
            )
        else:
            raw_results, assistant_message = _run_topic_search(library_id, search_run_id, user_request, source_names)
        if _run_status(library_id, search_run_id) == "cancelled":
            _append_run_event(library_id, search_run_id, "用户已取消本次检索，忽略迟到结果。", "warn")
            return
        _save_run_results(search_run_id, run, raw_results, "success")
        candidate_count = len(app_store.list_search_candidates(library_id))
        app_store.update_search_run(
            search_run_id,
            status="success",
            assistant_message=assistant_message,
            inserted_count=app_store.get_search_run(library_id, search_run_id).get("inserted_count", 0),
            deduped_count=app_store.get_search_run(library_id, search_run_id).get("deduped_count", 0),
            updated_count=app_store.get_search_run(library_id, search_run_id).get("updated_count", 0),
            candidate_count=candidate_count,
        )
        app_store.append_search_chat_message(
            library_id,
            role="assistant",
            content=assistant_message,
            mode=mode,
            search_run_id=search_run_id,
            inserted_count=int(app_store.get_search_run(library_id, search_run_id).get("inserted_count") or 0),
            candidate_count=candidate_count,
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc or "检索失败").strip() or "检索失败"
        app_store.update_search_run(search_run_id, status="failed", error_message=message, assistant_message="")
        app_store.append_search_chat_message(
            library_id,
            role="assistant",
            content=f"本次检索失败：{message}",
            mode=mode,
            search_run_id=search_run_id,
        )
        _append_run_event(library_id, search_run_id, f"检索失败：{message}", "error")
    finally:
        _trim_run_events(library_id, search_run_id)
        with _ACTIVE_SEARCH_WORKERS_LOCK:
            _ACTIVE_SEARCH_WORKERS.discard(search_run_id)


def _start_background_search(
    library_id: str,
    search_run_id: str,
    *,
    mode: str,
    user_request: str,
    source_names: list[str],
    compiled_queries: list[dict[str, Any]] | None = None,
) -> None:
    with _ACTIVE_SEARCH_WORKERS_LOCK:
        if search_run_id in _ACTIVE_SEARCH_WORKERS:
            return
        _ACTIVE_SEARCH_WORKERS.add(search_run_id)
    worker = threading.Thread(
        target=_execute_search_run,
        args=(library_id, search_run_id),
        kwargs={
            "mode": mode,
            "user_request": user_request,
            "source_names": source_names,
            "compiled_queries": compiled_queries,
        },
        daemon=True,
        name=f"search-{search_run_id}",
    )
    worker.start()


def queue_search(
    library_id: str,
    *,
    mode: str,
    user_request: str,
    source_names: list[str],
    compiled_queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_mode = normalize_search_mode(mode)
    clean_request = str(user_request or "").strip()
    if not clean_request:
        raise ValueError("检索词不能为空。")
    active = app_store.latest_running_search_run(library_id)
    if active:
        return {
            "search_run": active,
            "active_search_run": active,
            "latest_message": None,
            "candidates": app_store.list_search_candidates(library_id),
            "search_runs": app_store.list_search_runs(library_id),
            "search_messages": app_store.list_search_chat_messages(library_id),
            "search_events": app_store.list_search_run_events(library_id, active["search_run_id"]),
        }
    pending_run = app_store.create_search_run(
        library_id,
        mode=normalized_mode,
        user_request=clean_request,
        raw_results=[],
        context={"source_names": source_names, "compiled_queries": compiled_queries or []},
        status="queued",
    )
    user_message = app_store.append_search_chat_message(
        library_id,
        role="user",
        content=clean_request,
        mode=normalized_mode,
        search_run_id=pending_run["search_run_id"],
    )
    _append_run_event(library_id, pending_run["search_run_id"], "已创建检索任务，等待后台执行。")
    _start_background_search(
        library_id,
        pending_run["search_run_id"],
        mode=normalized_mode,
        user_request=clean_request,
        source_names=source_names,
        compiled_queries=compiled_queries,
    )
    return {
        "search_run": pending_run,
        "active_search_run": pending_run,
        "latest_message": user_message,
        "candidates": app_store.list_search_candidates(library_id),
        "search_runs": app_store.list_search_runs(library_id),
        "search_messages": app_store.list_search_chat_messages(library_id),
        "search_events": app_store.list_search_run_events(library_id, pending_run["search_run_id"]),
    }


def search_status(library_id: str) -> dict[str, Any]:
    recover_search_runs(library_id)
    active = app_store.latest_running_search_run(library_id)
    events = app_store.list_search_run_events(library_id, active["search_run_id"]) if active else []
    latest_run = app_store.list_search_runs(library_id)[:1]
    return {
        "running": bool(active),
        "active_search_run": active,
        "search_events": events,
        "search_messages": app_store.list_search_chat_messages(library_id),
        "candidates": app_store.list_search_candidates(library_id),
        "search_runs": app_store.list_search_runs(library_id),
        "last_completed_summary": latest_run[0].get("assistant_message", "") if latest_run else "",
    }


def cancel_active_search(library_id: str) -> dict[str, Any]:
    active = app_store.latest_running_search_run(library_id)
    if not active:
        return search_status(library_id)
    cancelled = app_store.cancel_search_run(library_id, active["search_run_id"])
    _append_run_event(library_id, active["search_run_id"], "用户已取消本次检索。", "warn")
    app_store.append_search_chat_message(
        library_id,
        role="assistant",
        content="本次检索已取消，若后台稍后返回结果，将不会再合并进候选池。",
        mode=str(active.get("mode") or ""),
        search_run_id=active["search_run_id"],
    )
    payload = search_status(library_id)
    payload["cancelled_search_run"] = cancelled
    return payload


def recover_search_runs(library_id: str) -> None:
    for run in app_store.list_search_runs(library_id):
        if str(run.get("status") or "") in {"queued", "running"}:
            search_run_id = str(run.get("search_run_id") or "")
            if not search_run_id:
                continue
            context = run.get("context") if isinstance(run.get("context"), dict) else {}
            _start_background_search(
                library_id,
                search_run_id,
                mode=str(run.get("mode") or "topic"),
                user_request=str(run.get("user_request") or ""),
                source_names=[str(item or "").strip().lower() for item in context.get("source_names") or [] if str(item or "").strip()],
                compiled_queries=context.get("compiled_queries") if isinstance(context.get("compiled_queries"), list) else [],
            )
