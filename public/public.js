const img = document.querySelector(".image img");
if (img) {
  const failed = () => {
    img.hidden = true;
    document.querySelector(".placeholder").hidden = false;
  };
  img.addEventListener("error", failed);
  if (img.complete && !img.naturalWidth) failed();
}
