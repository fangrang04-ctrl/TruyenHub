import threading
import uuid
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import close_old_connections, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import NovelImportForm
from .models import Chapter, Novel
from .views import create_or_update_imported_novel
from .importers.mtc import (
    MTCBrowserSession,
    fetch_mtc_chapter,
    fetch_mtc_chapters,
    fetch_mtc_novel,
)


JOB_TABLE = "novels_import_job"
JOB_TABLE_LOCK = threading.Lock()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_job_table():
    with JOB_TABLE_LOCK:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {JOB_TABLE} (
                    job_id VARCHAR(64) PRIMARY KEY,
                    status VARCHAR(20) NOT NULL,
                    progress INTEGER NOT NULL,
                    current_chapter INTEGER NOT NULL,
                    total_chapters INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    error TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    novel_id INTEGER NULL,
                    novel_title TEXT NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL
                )
                """
            )


def _new_job(source_url=""):
    _ensure_job_table()

    job_id = uuid.uuid4().hex
    now = _now()

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {JOB_TABLE} (
                job_id,
                status,
                progress,
                current_chapter,
                total_chapters,
                message,
                error,
                source_url,
                novel_id,
                novel_title,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job_id,
                "queued",
                0,
                0,
                0,
                "Đang chờ bắt đầu...",
                "",
                source_url,
                None,
                "",
                now,
                now,
            ),
        )

    return job_id


def _update_job(job_id, **values):
    _ensure_job_table()

    allowed = {
        "status": "status",
        "progress": "progress",
        "current": "current_chapter",
        "total": "total_chapters",
        "message": "message",
        "error": "error",
        "source_url": "source_url",
        "novel_id": "novel_id",
        "novel_title": "novel_title",
    }

    assignments = []
    params = []

    for key, value in values.items():
        column = allowed.get(key)

        if column is None:
            continue

        assignments.append(f"{column} = %s")
        params.append(value)

    if not assignments:
        return

    assignments.append("updated_at = %s")
    params.append(_now())
    params.append(job_id)

    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {JOB_TABLE} SET {', '.join(assignments)} WHERE job_id = %s",
            params,
        )


def _get_job(job_id):
    _ensure_job_table()

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                job_id,
                status,
                progress,
                current_chapter,
                total_chapters,
                message,
                error,
                source_url,
                novel_id,
                novel_title,
                created_at,
                updated_at
            FROM {JOB_TABLE}
            WHERE job_id = %s
            """,
            [job_id],
        )

        row = cursor.fetchone()

    if row is None:
        return None

    return {
        "job_id": row[0],
        "status": row[1],
        "progress": row[2],
        "current": row[3],
        "total": row[4],
        "message": row[5],
        "error": row[6],
        "source_url": row[7],
        "novel_id": row[8],
        "novel_title": row[9],
        "created_at": row[10],
        "updated_at": row[11],
    }


def _select_chapters(chapter_list, action, post_data):
    chapter_map = {
        int(item["number"]): item
        for item in chapter_list
    }

    if action == "import_one":
        value = post_data.get("chapter_number", "").strip()

        if not value:
            raise ValueError("Hãy nhập số chương cần lấy.")

        selected_numbers = [int(value)]

    elif action == "import_range":
        start_value = post_data.get("chapter_start", "").strip()
        end_value = post_data.get("chapter_end", "").strip()

        if not start_value or not end_value:
            raise ValueError(
                "Hãy nhập chương bắt đầu và chương kết thúc."
            )

        chapter_start = int(start_value)
        chapter_end = int(end_value)

        if chapter_start < 1 or chapter_end < 1:
            raise ValueError("Số chương phải lớn hơn 0.")

        if chapter_start > chapter_end:
            raise ValueError(
                "Chương bắt đầu không được lớn hơn chương kết thúc."
            )

        selected_numbers = list(
            range(
                chapter_start,
                chapter_end + 1,
            )
        )

    else:
        selected_numbers = sorted(chapter_map)

    missing_numbers = [
        number
        for number in selected_numbers
        if number not in chapter_map
    ]

    if missing_numbers:
        preview = ", ".join(
            str(number)
            for number in missing_numbers[:20]
        )

        if len(missing_numbers) > 20:
            preview += "..."

        raise ValueError(
            "Không tìm thấy chương: " + preview
        )

    return [
        chapter_map[number]
        for number in selected_numbers
    ]


def _run_import_job(job_id, source_url, user_id, action, post_data):
    browser_session = None

    try:
        close_old_connections()

        _update_job(
            job_id,
            status="running",
            progress=1,
            message="Đang mở nguồn truyện...",
        )

        from django.contrib.auth.models import User

        user = User.objects.get(id=user_id)

        browser_session = MTCBrowserSession()
        browser_session.start()

        _update_job(
            job_id,
            progress=3,
            message="Đang đọc thông tin truyện...",
        )

        imported_data = fetch_mtc_novel(
            source_url,
            browser_session=browser_session,
        )

        if not imported_data.get("title"):
            raise ValueError(
                "Không lấy được thông tin truyện từ nguồn."
            )

        imported_novel = create_or_update_imported_novel(
            source_url,
            imported_data,
            user,
        )

        _update_job(
            job_id,
            progress=8,
            novel_id=imported_novel.id,
            novel_title=imported_novel.title,
            message="Đang lấy danh sách chương...",
        )

        chapter_list = fetch_mtc_chapters(
            source_url,
            browser_session=browser_session,
        )

        if not chapter_list:
            raise ValueError(
                "Không lấy được danh sách chương từ nguồn."
            )

        if action == "load_chapters":
            _update_job(
                job_id,
                status="completed",
                progress=100,
                current=0,
                total=len(chapter_list),
                message=f"Đã tìm thấy {len(chapter_list)} chương.",
            )
            return

        selected_chapters = _select_chapters(
            chapter_list,
            action,
            post_data,
        )

        total = len(selected_chapters)

        _update_job(
            job_id,
            total=total,
            current=0,
            progress=8 if total else 100,
            message=f"Bắt đầu import {total} chương...",
        )

        for index, source_chapter in enumerate(
            selected_chapters,
            start=1,
        ):
            number = int(source_chapter["number"])

            _update_job(
                job_id,
                current=index - 1,
                progress=max(
                    8,
                    min(
                        99,
                        int(
                            8
                            + ((index - 1) / max(total, 1)) * 91
                        )
                    ),
                ),
                message=f"Đang import chương {number} ({index}/{total})...",
            )

            chapter_data = fetch_mtc_chapter(
                source_chapter["url"],
                browser_session=browser_session,
            )

            title = chapter_data.get("title", "")
            content = chapter_data.get("content", "")

            if not content or len(content.strip()) < 50:
                raise ValueError(
                    f"Không lấy được nội dung chương {number}."
                )

            Chapter.objects.update_or_create(
                novel=imported_novel,
                chapter_number=number,
                defaults={
                    "title": title or source_chapter.get(
                        "name",
                        f"Chương {number}",
                    ),
                    "content": content,
                    "status": "published",
                },
            )

            progress = int(
                8 + (index / max(total, 1)) * 91
            )

            _update_job(
                job_id,
                current=index,
                progress=max(8, min(99, progress)),
                message=f"Đã import chương {number} ({index}/{total}).",
            )

        _update_job(
            job_id,
            status="completed",
            progress=100,
            current=total,
            total=total,
            message=f"Đã import xong {total} chương.",
        )

    except Exception as error:
        _update_job(
            job_id,
            status="error",
            progress=0,
            message="Import thất bại.",
            error=str(error),
        )

    finally:
        try:
            if browser_session is not None:
                browser_session.close()
        except Exception:
            pass

        close_old_connections()


@login_required
def import_novel(request):
    form = NovelImportForm()

    imported_data = None
    imported_novel = None
    chapter_list = []
    error_message = None
    success_message = None

    if request.method == "POST":
        form = NovelImportForm(request.POST)

        if form.is_valid():
            source_url = form.cleaned_data["source_url"]
            action = request.POST.get("action", "")

            if action in {
                "preview",
                "save_novel",
            }:
                try:
                    imported_data = fetch_mtc_novel(source_url)

                    if action == "save_novel":
                        imported_novel = (
                            create_or_update_imported_novel(
                                source_url,
                                imported_data,
                                request.user,
                            )
                        )
                        success_message = (
                            "Đã nhập thông tin truyện vào TruyenHub."
                        )

                except Exception as error:
                    error_message = str(error)

            elif action in {
                "load_chapters",
                "import_one",
                "import_range",
                "import_all",
            }:
                try:
                    imported_novel = Novel.objects.filter(
                        source_url=source_url
                    ).first()

                    if imported_novel is None:
                        imported_data = fetch_mtc_novel(source_url)
                        imported_novel = (
                            create_or_update_imported_novel(
                                source_url,
                                imported_data,
                                request.user,
                            )
                        )

                    job_id = _new_job(source_url)

                    thread = threading.Thread(
                        target=_run_import_job,
                        args=(
                            job_id,
                            source_url,
                            request.user.id,
                            action,
                            request.POST.dict(),
                        ),
                        daemon=True,
                    )
                    thread.start()

                    request.session["last_import_job_id"] = job_id
                    request.session.modified = True

                    return render(
                        request,
                        "novels/import_novel.html",
                        {
                            "form": form,
                            "imported_data": imported_data,
                            "imported_novel": imported_novel,
                            "chapter_list": chapter_list,
                            "error_message": None,
                            "success_message": None,
                            "import_job_id": job_id,
                        },
                    )

                except Exception as error:
                    error_message = str(error)

    if imported_novel:
        existing_numbers = set(
            imported_novel.chapters.values_list(
                "chapter_number",
                flat=True,
            )
        )

        for item in chapter_list:
            item["imported"] = item["number"] in existing_numbers

    return render(
        request,
        "novels/import_novel.html",
        {
            "form": form,
            "imported_data": imported_data,
            "imported_novel": imported_novel,
            "chapter_list": chapter_list,
            "error_message": error_message,
            "success_message": success_message,
            "import_job_id": request.session.get(
                "last_import_job_id",
                "",
            ),
        },
    )


@login_required
@require_POST
def start_import(request):
    source_url = request.POST.get("source_url", "").strip()
    action = request.POST.get("action", "import_all").strip()

    if not source_url:
        return JsonResponse(
            {
                "ok": False,
                "error": "Thiếu URL truyện.",
            },
            status=400,
        )

    if action not in {
        "load_chapters",
        "import_one",
        "import_range",
        "import_all",
    }:
        action = "import_all"

    job_id = _new_job(source_url)

    thread = threading.Thread(
        target=_run_import_job,
        args=(
            job_id,
            source_url,
            request.user.id,
            action,
            request.POST.dict(),
        ),
        daemon=True,
    )
    thread.start()

    return JsonResponse(
        {
            "ok": True,
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "current": 0,
            "total": 0,
            "message": "Đã bắt đầu import.",
        }
    )


@login_required
def import_status(request):
    job_id = request.GET.get("job_id", "").strip()

    if not job_id:
        return JsonResponse(
            {
                "ok": False,
                "error": "Thiếu job_id.",
            },
            status=400,
        )

    job = _get_job(job_id)

    if job is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Không tìm thấy tiến trình import.",
            },
            status=404,
        )

    job["ok"] = True
    return JsonResponse(job)
