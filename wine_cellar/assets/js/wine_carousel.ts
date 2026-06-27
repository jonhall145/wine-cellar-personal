document.addEventListener("DOMContentLoaded", function () {
    const wrapper = document.querySelector(".wine-detail__image-wrapper") as HTMLElement | null;
    if (!wrapper) return;

    const previewImages = Array.from(
        wrapper.querySelectorAll("[data-preview-image]"),
    ) as HTMLImageElement[];
    if (previewImages.length === 0) return;

    const prevBtn = wrapper.querySelector(".wine-prev") as HTMLButtonElement | null;
    const nextBtn = wrapper.querySelector(".wine-next") as HTMLButtonElement | null;
    const openButtons = document.querySelectorAll("[data-image-viewer-open]");
    const viewer = document.getElementById("beverage-image-viewer") as HTMLElement | null;
    const viewerStage = document.getElementById(
        "beverage-image-viewer-stage",
    ) as HTMLElement | null;
    const viewerImages = Array.from(
        viewer?.querySelectorAll("[data-image-viewer-image]") ?? [],
    ) as HTMLImageElement[];
    const viewerLinks = Array.from(
        viewer?.querySelectorAll("[data-image-viewer-link]") ?? [],
    ) as HTMLAnchorElement[];
    const viewerCount = document.getElementById(
        "beverage-image-viewer-count",
    ) as HTMLElement | null;
    const viewerPrev = viewer?.querySelector(
        "[data-image-viewer-prev]",
    ) as HTMLButtonElement | null;
    const viewerNext = viewer?.querySelector(
        "[data-image-viewer-next]",
    ) as HTMLButtonElement | null;
    const zoomOutButton = viewer?.querySelector(
        "[data-image-viewer-zoom-out]",
    ) as HTMLButtonElement | null;
    const zoomInButton = viewer?.querySelector(
        "[data-image-viewer-zoom-in]",
    ) as HTMLButtonElement | null;
    const zoomResetButton = viewer?.querySelector(
        "[data-image-viewer-reset]",
    ) as HTMLButtonElement | null;
    const closeButtons = viewer?.querySelectorAll("[data-image-viewer-close]");

    let index = 0;
    let zoom = 1;
    let lastFocusedBeforeOpen: HTMLElement | null = null;

    const MIN_ZOOM = 1;
    const MAX_ZOOM = 4;
    const ZOOM_STEP = 0.5;

    function currentViewerImage(): HTMLImageElement | null {
        return viewerImages[index] ?? null;
    }

    function setViewerNavigationState() {
        if (!viewerPrev || !viewerNext) return;

        const disabled = previewImages.length <= 1;
        viewerPrev.disabled = disabled;
        viewerNext.disabled = disabled;
    }

    function setZoomState() {
        if (!zoomOutButton || !zoomInButton || !zoomResetButton) return;

        zoomOutButton.disabled = zoom <= MIN_ZOOM;
        zoomInButton.disabled = zoom >= MAX_ZOOM;
        zoomResetButton.textContent = `${Math.round(zoom * 100)}%`;
        zoomResetButton.disabled = zoom === 1;
    }

    function applyZoom(resetScroll = false) {
        const viewerImage = currentViewerImage();
        if (!viewerStage || !viewerImage || !viewerImage.naturalWidth || !viewerImage.naturalHeight) {
            setZoomState();
            return;
        }

        const availableWidth = Math.max(viewerStage.clientWidth - 32, 1);
        const availableHeight = Math.max(viewerStage.clientHeight - 32, 1);
        const fitScale = Math.min(
            availableWidth / viewerImage.naturalWidth,
            availableHeight / viewerImage.naturalHeight,
            1,
        );
        const displayScale = fitScale * zoom;

        viewerImage.style.width = `${Math.round(viewerImage.naturalWidth * displayScale)}px`;
        viewerImage.style.height = `${Math.round(viewerImage.naturalHeight * displayScale)}px`;

        if (resetScroll) {
            viewerStage.scrollTop = 0;
            viewerStage.scrollLeft = 0;
        }

        setZoomState();
    }

    function setIndex(nextIndex: number) {
        index = (nextIndex + previewImages.length) % previewImages.length;

        previewImages.forEach((image, imageIndex) => {
            image.hidden = imageIndex !== index;
        });

        viewerImages.forEach((image, imageIndex) => {
            image.hidden = imageIndex !== index;
        });

        viewerLinks.forEach((link, linkIndex) => {
            link.hidden = linkIndex !== index;
        });

        if (viewerCount) {
            viewerCount.textContent = `Photo ${index + 1} of ${previewImages.length}`;
        }
    }

    function resetZoom() {
        zoom = 1;
        applyZoom(true);
    }

    function changeImage(step: number) {
        setIndex(index + step);
        resetZoom();
    }

    function openViewer() {
        if (!viewer) return;

        lastFocusedBeforeOpen = document.activeElement as HTMLElement | null;
        viewer.hidden = false;
        document.body.style.overflow = "hidden";
        setIndex(index);
        resetZoom();
        (viewer.querySelector("[data-image-viewer-close]") as HTMLButtonElement | null)?.focus();
    }

    function closeViewer() {
        if (!viewer) return;

        viewer.hidden = true;
        document.body.style.overflow = "";
        if (lastFocusedBeforeOpen?.isConnected) {
            lastFocusedBeforeOpen.focus();
        }
        lastFocusedBeforeOpen = null;
    }

    if (prevBtn) {
        prevBtn.addEventListener("click", () => {
            changeImage(-1);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            changeImage(1);
        });
    }

    openButtons.forEach((button) => {
        button.addEventListener("click", openViewer);
    });

    viewerPrev?.addEventListener("click", () => {
        changeImage(-1);
    });

    viewerNext?.addEventListener("click", () => {
        changeImage(1);
    });

    zoomOutButton?.addEventListener("click", () => {
        zoom = Math.max(MIN_ZOOM, zoom - ZOOM_STEP);
        applyZoom();
    });

    zoomInButton?.addEventListener("click", () => {
        zoom = Math.min(MAX_ZOOM, zoom + ZOOM_STEP);
        applyZoom();
    });

    zoomResetButton?.addEventListener("click", resetZoom);

    closeButtons?.forEach((button) => {
        button.addEventListener("click", closeViewer);
    });

    viewerImages.forEach((image) => {
        image.addEventListener("load", () => {
            if (!image.hidden) {
                applyZoom(true);
            }
        });
    });

    viewerImages.forEach((image) => {
        image.addEventListener("dblclick", () => {
            zoom = zoom === 1 ? 2 : 1;
            applyZoom();
        });
    });

    window.addEventListener("resize", () => {
        if (!viewer?.hidden) {
            applyZoom();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (viewer?.hidden) return;

        if (event.key === "Escape") {
            closeViewer();
            return;
        }

        if (event.key === "ArrowLeft") {
            changeImage(-1);
            return;
        }

        if (event.key === "ArrowRight") {
            changeImage(1);
            return;
        }

        if (event.key === "+" || event.key === "=") {
            zoom = Math.min(MAX_ZOOM, zoom + ZOOM_STEP);
            applyZoom();
            return;
        }

        if (event.key === "-") {
            zoom = Math.max(MIN_ZOOM, zoom - ZOOM_STEP);
            applyZoom();
            return;
        }

        if (event.key === "0") {
            resetZoom();
        }
    });

    setViewerNavigationState();
    setIndex(0);
    setZoomState();
});
