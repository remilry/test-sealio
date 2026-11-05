import * as UTIF from "utif";

/**
 * Images of a rendered Word document that the browser cannot show: a TIFF (a scanned logo, often)
 * is decoded and shown as a PNG; anything else unreadable keeps its room, without a broken icon.
 */
export async function showImages(root: HTMLElement): Promise<void> {
  await Promise.all([...root.querySelectorAll("img")].map(showImage));
}

async function showImage(image: HTMLImageElement): Promise<void> {
  const hide = () => {
    image.style.visibility = "hidden";
  };
  try {
    const bytes = await (await fetch(image.src)).arrayBuffer();
    if (isTiff(new Uint8Array(bytes))) {
      image.src = tiffToPng(bytes);
      return;
    }
  } catch {
    // Not readable here: left to the browser, hidden if it cannot show it either.
  }
  if (image.complete && image.naturalWidth === 0) hide();
  else image.addEventListener("error", hide, { once: true });
}

function isTiff(bytes: Uint8Array): boolean {
  const [a, b, c, d] = bytes;
  return (
    (a === 0x49 && b === 0x49 && c === 0x2a && d === 0) ||
    (a === 0x4d && b === 0x4d && c === 0 && d === 0x2a)
  );
}

function tiffToPng(bytes: ArrayBuffer): string {
  const [page] = UTIF.decode(bytes);
  UTIF.decodeImage(bytes, page);
  const rgba = UTIF.toRGBA8(page);
  const width = Number(page.width);
  const height = Number(page.height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas
    .getContext("2d")
    ?.putImageData(new ImageData(new Uint8ClampedArray(rgba), width, height), 0, 0);
  return canvas.toDataURL("image/png");
}
