import axios from "axios";

/* ---------- 创建 axios 实例 ---------- */
export const api = axios.create({
  baseURL: "https://recordsystem.onrender.com/",  // 后端地址，结尾不要斜杠
  withCredentials: false,           // 若以后要带 cookie 再改
});

/* ---------- 统一响应拦截器 ---------- */
api.interceptors.response.use(
  (res) => res,                          // 2xx 正常通过
  (error) => {
    // 非 2xx：读取后端 detail 并 alert
    const msg =
      error.response?.data?.detail ||
      error.response?.data?.message ||   // 有时 FastAPI 用 message
      "服务器错误";
    alert(msg);
    return Promise.reject(error);        // 继续抛给调用方（如需）
  }
);

/* ---------- 封装各接口 ---------- */
export const getFigures   = () => api.get("/figures");
export const createFigure = (formData) => api.post("/figures/", formData);

export const deleteFigure = (id) => api.delete(`/figures/${id}`);

export const inbound  = (data) => api.post("/stock/inbound",  data);
export const outbound = (data) => api.post("/stock/outbound", data);

// 对于图片，现已是绝对 URL，保留防御式写法
export const apiJoin = (path) => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  const BASE = String(base).replace(/\/+$/, "");
  return `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
};