/** Re-encode browser uploads to remove embedded EXIF, including GPS metadata. */
export async function stripImageMetadata(file: File): Promise<File> {
  if (typeof createImageBitmap === "undefined") {
    throw new Error("This browser cannot safely prepare photos for upload.");
  }
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("We could not prepare that photo.");
    context.drawImage(bitmap, 0, 0);
    const clean = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("We could not prepare that photo.")), file.type);
    });
    return new File([clean], file.name, { type: file.type, lastModified: Date.now() });
  } finally {
    bitmap.close();
  }
}
