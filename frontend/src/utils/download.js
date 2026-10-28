/** Guarda en el equipo un archivo recibido como blob (axios), usando el nombre que envía el servidor. */
export function saveBlobResponse(response, fallbackName) {
  const disposition = response.headers?.["content-disposition"] || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function readBlobText(blob) {
  if (typeof blob.text === "function") return blob.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

/** Los errores de una descarga llegan como Blob: se convierten a JSON para mostrar el mensaje del backend. */
export async function blobErrorToJson(error) {
  const blob = error?.response?.data;
  if (blob instanceof Blob) {
    try {
      error.response.data = JSON.parse(await readBlobText(blob));
    } catch {
      error.response.data = {};
    }
  }
  return error;
}
