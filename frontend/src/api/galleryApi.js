import { api, authHeaders } from "./client";

export function getGalleryPhotos() {
  return api.get("/gallery/photos");
}

export function galleryPhotoImageUrl(photoId) {
  return `${api.defaults.baseURL}/gallery/photos/${photoId}/image`;
}

export function submitGalleryPhoto(file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/gallery/photos", formData, { headers: authHeaders() });
}

export function getAdminGalleryPhotos(status) {
  return api.get("/gallery/admin/photos", {
    headers: authHeaders(),
    params: status === "all" ? {} : { status },
  });
}

export function getAdminGalleryPhotoImage(photoId) {
  return api.get(`/gallery/admin/photos/${photoId}/image`, {
    headers: authHeaders(),
    responseType: "blob",
  });
}

export function updateGalleryPhoto(photoId, data) {
  return api.patch(`/gallery/admin/photos/${photoId}/update`, data, {
    headers: authHeaders(),
  });
}

export function deleteGalleryPhoto(photoId) {
  return api.delete(`/gallery/admin/photos/${photoId}`, {
    headers: authHeaders(),
  });
}
