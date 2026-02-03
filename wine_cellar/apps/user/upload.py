import os
import re
from datetime import datetime, timezone
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView
from django_ratelimit.decorators import ratelimit

UPLOAD_DIR = Path(settings.MEDIA_ROOT) / "uploads" / "css"
MAX_FILE_SIZE = 512 * 1024  # 500KB
MAX_FILES = 10

# Patterns that should never appear in a CSS file
DANGEROUS_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"behavior\s*:", re.IGNORECASE),
    re.compile(r"-moz-binding\s*:", re.IGNORECASE),
    re.compile(r"<\s*/?\s*\w+", re.IGNORECASE),  # any HTML tags
]


class CSSUploadForm(forms.Form):
    file = forms.FileField(
        label="CSS file",
        help_text="Upload a .css file (max 500KB).",
        widget=forms.ClearableFileInput(attrs={"accept": ".css"}),
    )

    def clean_file(self):
        f = self.cleaned_data["file"]

        # Check extension
        if not f.name.lower().endswith(".css"):
            raise forms.ValidationError("Only .css files are allowed.")

        # Check size
        if f.size > MAX_FILE_SIZE:
            raise forms.ValidationError("File must be under 500KB.")

        # Check content is valid UTF-8 text
        try:
            content = f.read().decode("utf-8")
            f.seek(0)
        except (UnicodeDecodeError, AttributeError):
            raise forms.ValidationError("File must be valid UTF-8 text.")

        # Check for dangerous content
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(content):
                raise forms.ValidationError(
                    "File contains disallowed content (HTML or script injection)."
                )

        return f


def _get_uploaded_files():
    """Return list of uploaded CSS files with metadata, newest first."""
    if not UPLOAD_DIR.exists():
        return []
    files = []
    for p in UPLOAD_DIR.iterdir():
        if p.is_file() and p.suffix.lower() == ".css":
            stat = p.stat()
            files.append(
                {
                    "name": p.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                }
            )
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


def _enforce_file_limit():
    """Delete oldest files if over the limit."""
    files = _get_uploaded_files()
    while len(files) > MAX_FILES:
        oldest = files.pop()
        (UPLOAD_DIR / oldest["name"]).unlink(missing_ok=True)


@method_decorator(
    ratelimit(key="user", rate="10/m", method="POST", block=True),
    name="post",
)
class CSSUploadView(FormView):
    template_name = "upload_css.html"
    form_class = CSSUploadForm
    success_url = reverse_lazy("css-upload")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["uploaded_files"] = _get_uploaded_files()
        return ctx

    def form_valid(self, form):
        f = form.cleaned_data["file"]

        # Sanitize filename: keep only alphanumeric, hyphens, underscores, dots
        safe_name = re.sub(r"[^\w.\-]", "_", f.name)
        if not safe_name.lower().endswith(".css"):
            safe_name += ".css"

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        dest = UPLOAD_DIR / safe_name
        with open(dest, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)

        _enforce_file_limit()
        messages.success(self.request, f"Uploaded {safe_name}.")
        return super().form_valid(form)


def delete_css_file(request):
    """Delete a specific uploaded CSS file."""
    if request.method != "POST":
        return HttpResponseRedirect(reverse_lazy("css-upload"))

    filename = request.POST.get("filename", "")
    # Prevent path traversal
    safe = os.path.basename(filename)
    if not safe or not safe.lower().endswith(".css"):
        messages.error(request, "Invalid file.")
        return HttpResponseRedirect(reverse_lazy("css-upload"))

    target = UPLOAD_DIR / safe
    if target.exists() and target.is_file():
        target.unlink()
        messages.success(request, f"Deleted {safe}.")
    else:
        messages.error(request, "File not found.")

    return HttpResponseRedirect(reverse_lazy("css-upload"))
