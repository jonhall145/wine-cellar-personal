document.addEventListener("DOMContentLoaded", function () {
    const wrapper = document.querySelector(".wine-detail__image-wrapper") as HTMLElement;
    if (!wrapper) return;

    const images = JSON.parse(wrapper.dataset.images || '[]');
    if (images.length <= 1) return;

    let index = 0;

    const imgEl = document.getElementById("wine-image") as HTMLImageElement;
    const prevBtn = wrapper.querySelector(".wine-prev") as HTMLButtonElement;
    const nextBtn = wrapper.querySelector(".wine-next") as HTMLButtonElement;

    if (!imgEl || !prevBtn || !nextBtn) return;

    function updateImage() {
        imgEl.src = images[index];
    }

    prevBtn.addEventListener("click", () => {
        index = (index - 1 + images.length) % images.length;
        updateImage();
    });

    nextBtn.addEventListener("click", () => {
        index = (index + 1) % images.length;
        updateImage();
    });
});
