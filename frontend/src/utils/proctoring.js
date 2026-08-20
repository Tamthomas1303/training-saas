// Tien ich webcam + phat hien khuon mat client-side cho giam sat thi (Giai doan A -
// Prompt_ChongGianLan_Thi_Video.md). Thu vien phat hien khuon mat (@vladmandic/face-api, ban
// fork con duy tri cua face-api.js goc, co kem san model weights trong npm package) duoc tai TU
// CDN (jsdelivr) luc runtime - KHONG bundle qua vite, vi model nang va chi can khi de bat
// proctoring. Da xac minh truc tiep URL nay tra ve 200 truoc khi dua vao (dist/face-api.js +
// model/tiny_face_detector_model*).
//
// Neu CDN/model tai loi (mang chan, offline...) thi CHI mat phan phat hien khuon mat - webcam
// preview + chup snapshot + cac lop chan khac (roi tab, copy/paste, fullscreen) VAN hoat dong
// binh thuong. Dung dung tinh than "ran de, KHONG chan 100%" cua prompt - khong bao gio de loi
// tai thu vien lam sap ca man thi.
const FACE_API_LIB_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/dist/face-api.js'
const FACE_API_MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/model/'

let loadPromise = null

export function loadFaceApi() {
  if (typeof window === 'undefined') return Promise.reject(new Error('Không có window'))
  if (window.faceapi?.nets?.tinyFaceDetector?.isLoaded) return Promise.resolve(window.faceapi)
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    function afterLibLoaded() {
      window.faceapi.nets.tinyFaceDetector.loadFromUri(FACE_API_MODEL_URL)
        .then(() => resolve(window.faceapi))
        .catch(reject)
    }
    if (window.faceapi) {
      afterLibLoaded()
      return
    }
    const script = document.createElement('script')
    script.src = FACE_API_LIB_URL
    script.async = true
    script.onload = afterLibLoaded
    script.onerror = () => reject(new Error('Không tải được thư viện nhận diện khuôn mặt (CDN).'))
    document.head.appendChild(script)
  }).catch((err) => {
    loadPromise = null // cho phep thu lai lan sau (vd mang vua on dinh lai)
    throw err
  })
  return loadPromise
}

export async function detectFaceCount(faceapi, videoEl) {
  if (!videoEl || videoEl.readyState < 2) return null // chua co frame nao de doc
  const detections = await faceapi.detectAllFaces(videoEl, new faceapi.TinyFaceDetectorOptions())
  return detections.length
}

// Nen anh nho (mac dinh rong toi da 320px) truoc khi gui len server - dung y prompt "anh nho,
// nen" (snapshot chi de doi chieu, khong can chat luong cao).
export function captureSnapshotDataUrl(videoEl, maxWidth = 320) {
  const vw = videoEl.videoWidth || maxWidth
  const vh = videoEl.videoHeight || Math.round(maxWidth * 0.75)
  const scale = Math.min(1, maxWidth / vw)
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(vw * scale))
  canvas.height = Math.max(1, Math.round(vh * scale))
  const ctx = canvas.getContext('2d')
  ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.5)
}
