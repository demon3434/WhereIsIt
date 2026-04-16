const state = {
  token: localStorage.getItem("whereisit_token") || "",
  me: null,
  houses: [],
  rooms: [],
  roomInlineEdit: null,
  categories: [],
  tags: [],
  items: [],
  itemKeyword: "",
  itemHouseId: "",
  itemRoomId: "",
  itemCategoryId: "",
  itemTagId: "",
  itemTagKeyword: "",
  itemPage: 1,
  itemPageSize: 20,
  itemTotal: 0,
  itemTotalPages: 0,
  itemSortKey: "updated_at",
  itemSortOrder: "desc",
  users: [],
  pendingFiles: [],
  selectedItemTags: [],
  editPendingFiles: [],
  editRemovedImageIds: [],
  selectedEditItemTags: [],
  houseInlineEdit: null,
  houseKeyword: "",
  houseStatus: "",
  housePage: 1,
  housePageSize: 10,
  categoryInlineEdit: null,
  categoryKeyword: "",
  categoryStatus: "",
  categoryPage: 1,
  categoryPageSize: 10,
  tagInlineEdit: null,
  tagKeyword: "",
  tagStatus: "",
  tagPage: 1,
  tagPageSize: 10,
  userInlineEdit: null,
  userKeyword: "",
  userStatus: "",
  userRole: "",
  userPage: 1,
  userPageSize: 10,
  adminAvailableOpen: false,
};

const byId = (id) => document.getElementById(id);

const authSection = byId("authSection");
const mainSection = byId("mainSection");
const loginPage = byId("loginPage");
const currentUser = byId("currentUser");
const currentUserBtn = byId("currentUserBtn");
const userMenuWrap = byId("userMenuWrap");
const userMenu = byId("userMenu");
const logoutBtn = byId("logoutBtn");

const itemTagInput = byId("itemTagInput");
const itemTagChips = byId("itemTagChips");
const itemTagOptions = byId("itemTagOptions");
const itemEditTagInput = byId("itemEditTagInput");
const itemEditTagChips = byId("itemEditTagChips");
const itemEditTagOptions = byId("itemEditTagOptions");

const itemDetailDialog = byId("itemDetailDialog");
const itemPhotosDialog = byId("itemPhotosDialog");
const itemEditDialog = byId("itemEditDialog");
const imagePreviewDialog = byId("imagePreviewDialog");
const imagePreviewImg = byId("imagePreviewImg");
const imagePreviewCloseBtn = byId("imagePreviewCloseBtn");
const imagePreviewTitle = byId("imagePreviewTitle");
const imageZoomInBtn = byId("imageZoomInBtn");
const imageZoomOutBtn = byId("imageZoomOutBtn");
const imageZoomResetBtn = byId("imageZoomResetBtn");
const imagePreviewStage = byId("imagePreviewStage");

const confirmDialog = byId("confirmDialog");
const confirmTitle = byId("confirmTitle");
const confirmSummary = byId("confirmSummary");
const confirmDetails = byId("confirmDetails");
const confirmCancelBtn = byId("confirmCancelBtn");
const confirmOkBtn = byId("confirmOkBtn");

let previewScale = 1;
const MAX_IMAGES_PER_ITEM = 9;
const UPLOAD_IMAGE_MAX_BYTES = 900 * 1024;
const UPLOAD_IMAGE_MAX_LONG_EDGE = 1600;
const UPLOAD_IMAGE_MIN_LONG_EDGE = 720;
const UPLOAD_IMAGE_INITIAL_QUALITY = 0.82;
const UPLOAD_IMAGE_MIN_QUALITY = 0.56;
const UPLOAD_IMAGE_QUALITY_STEP = 0.08;
const UPLOAD_IMAGE_SCALE_STEP = 0.85;

function toast(msg) {
  window.alert(msg);
}

function clampUploadQuality(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function toUploadJpegName(name = "upload") {
  const base = String(name || "upload")
    .replace(/\.[^.]+$/, "")
    .replace(/[^\w.-]+/g, "_");
  return `${base || "upload"}.jpg`;
}

function scaleByLongEdge(width, height, targetLongEdge) {
  const safeW = Math.max(1, Math.round(width || 1));
  const safeH = Math.max(1, Math.round(height || 1));
  const longEdge = Math.max(safeW, safeH);
  if (longEdge <= targetLongEdge) return { width: safeW, height: safeH };
  const ratio = targetLongEdge / longEdge;
  return {
    width: Math.max(1, Math.round(safeW * ratio)),
    height: Math.max(1, Math.round(safeH * ratio)),
  };
}

function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => resolve({ image, cleanup: () => URL.revokeObjectURL(objectUrl) });
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error(`图片“${file.name || "未命名"}”读取失败`));
    };
    image.src = objectUrl;
  });
}

function drawImageToCanvas(image, width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("浏览器不支持 Canvas 2D");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);
  return canvas;
}

function canvasToJpegBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("图片编码失败"));
      },
      "image/jpeg",
      clampUploadQuality(quality)
    );
  });
}

async function compressImageForUpload(file) {
  if (!file || !String(file.type || "").startsWith("image/")) {
    throw new Error(`文件“${file?.name || "未命名"}”不是图片`);
  }

  const { image, cleanup } = await loadImageElement(file);
  try {
    const sourceWidth = image.naturalWidth || image.width || 1;
    const sourceHeight = image.naturalHeight || image.height || 1;
    let size = scaleByLongEdge(sourceWidth, sourceHeight, UPLOAD_IMAGE_MAX_LONG_EDGE);
    let longEdge = Math.max(size.width, size.height);
    let quality = UPLOAD_IMAGE_INITIAL_QUALITY;
    let canvas = drawImageToCanvas(image, size.width, size.height);

    while (true) {
      const blob = await canvasToJpegBlob(canvas, quality);
      if (blob.size <= UPLOAD_IMAGE_MAX_BYTES) {
        return new File([blob], toUploadJpegName(file.name), {
          type: "image/jpeg",
          lastModified: Date.now(),
        });
      }
      if (quality > UPLOAD_IMAGE_MIN_QUALITY + 1e-6) {
        quality = Math.max(UPLOAD_IMAGE_MIN_QUALITY, quality - UPLOAD_IMAGE_QUALITY_STEP);
        continue;
      }
      if (longEdge <= UPLOAD_IMAGE_MIN_LONG_EDGE) break;

      const nextLongEdge = Math.max(UPLOAD_IMAGE_MIN_LONG_EDGE, Math.floor(longEdge * UPLOAD_IMAGE_SCALE_STEP));
      if (nextLongEdge >= longEdge) break;

      size = scaleByLongEdge(size.width, size.height, nextLongEdge);
      longEdge = Math.max(size.width, size.height);
      canvas = drawImageToCanvas(image, size.width, size.height);
      quality = UPLOAD_IMAGE_INITIAL_QUALITY;
    }

    throw new Error(`图片“${file.name || "未命名"}”压缩后仍超过 900KB，请更换图片`);
  } finally {
    cleanup();
  }
}

async function compressFilesForUpload(files) {
  const output = [];
  for (const file of files) {
    output.push(await compressImageForUpload(file));
  }
  return output;
}

function escapeHtml(raw) {
  return String(raw)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDateTime(value, withSeconds = false) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const hm = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  if (!withSeconds) return `${base} ${hm}`;
  return `${base} ${hm}:${pad(date.getSeconds())}`;
}

function formatDateOnly(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10) || "-";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function ellipsisByChars(text, maxChars) {
  const value = String(text || "");
  const chars = [...value];
  if (chars.length <= maxChars) return value;
  return `${chars.slice(0, maxChars).join("")}...`;
}

function setPreviewScale(nextScale) {
  previewScale = Math.max(0.2, Math.min(4, Number(nextScale) || 1));
  if (imagePreviewImg) imagePreviewImg.style.transform = `scale(${previewScale})`;
}

function openImagePreview(url, alt = "图片预览", titleText = "") {
  if (!imagePreviewDialog || !imagePreviewImg || !url) return;
  imagePreviewImg.src = url;
  imagePreviewImg.alt = alt;
  if (imagePreviewTitle) imagePreviewTitle.textContent = titleText || alt;
  setPreviewScale(1);
  imagePreviewDialog.showModal();
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => null);
  const envelope =
    data && typeof data === "object" && !Array.isArray(data) && "code" in data && "message" in data && "data" in data
      ? data
      : null;

  if (!res.ok) {
    if (envelope) throw new Error(envelope.message || "????");
    throw new Error(data?.detail || data?.message || "????");
  }

  if (envelope) {
    if (Number(envelope.code || 0) !== 0) throw new Error(envelope.message || "????");
    return envelope.data;
  }
  return data ?? {};
}

function setToken(token) {
  state.token = token;
  if (token) localStorage.setItem("whereisit_token", token);
  else localStorage.removeItem("whereisit_token");
}

function switchAuthPage(page) {
  loginPage.classList.toggle("hidden", page !== "login");
}

function pathToTab() {
  const p = window.location.pathname.toLowerCase();
  if (p === "/locations") return "locations";
  if (p === "/categories") return "categories";
  if (p === "/tags") return "tags";
  if (p === "/users") return "users";
  if (p === "/data-management") return "data";
  if (p === "/profile") return "profile";
  return "items";
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.add("hidden"));
  byId(`${name}Tab`)?.classList.remove("hidden");
}

function finishBoot() {
  document.body.classList.remove("booting");
}

function bindTopTabNavigation() {
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", (e) => {
      if (!state.token) return;
      e.preventDefault();
      const href = tab.getAttribute("href");
      if (href && window.location.pathname !== href) history.pushState({}, "", href);
      switchTab(tab.dataset.tab);
      if (tab.dataset.tab === "locations") switchLocationSubTab("house");
      closeUserMenu();
    });
  });

  const brand = document.querySelector(".brand-tab");
  if (brand) {
    brand.addEventListener("click", (e) => {
      if (!state.token) return;
      e.preventDefault();
      if (window.location.pathname !== "/items") history.pushState({}, "", "/items");
      switchTab("items");
      closeUserMenu();
    });
  }

  window.addEventListener("popstate", () => {
    if (!state.token) return;
    switchTab(pathToTab());
  });
}

function switchLocationSubTab(name) {
  document.querySelectorAll(".location-subtab").forEach((btn) => btn.classList.toggle("active", btn.dataset.locTab === name));
  byId("locationHousePanel").classList.toggle("hidden", name !== "house");
  byId("locationRoomPanel").classList.toggle("hidden", name !== "room");
}

function switchItemSubTab(name) {
  document.querySelectorAll(".item-subtab").forEach((btn) => btn.classList.toggle("active", btn.dataset.itemTab === name));
  byId("itemCreatePanel").classList.toggle("hidden", name !== "create");
  byId("itemListPanel").classList.toggle("hidden", name !== "list");
}

function optionList(data, emptyLabel = "全部") {
  return `<option value="">${emptyLabel}</option>` + data.map((it) => `<option value="${it.id}">${escapeHtml(it.name || it.path)}</option>`).join("");
}

function getCurrentUserAvailableHouseIds() {
  if (state.me?.role === "admin") return state.houses.filter((h) => h.is_active).map((h) => Number(h.id));
  return (state.me?.available_house_ids || []).map((id) => Number(id));
}
function getActiveAvailableHouses(availableIds) {
  const allowed = new Set((availableIds || []).map((id) => Number(id)));
  return state.houses.filter((house) => house.is_active && allowed.has(Number(house.id)));
}
function getSelectedValues(selectEl) {
  return Array.from(selectEl?.selectedOptions || [])
    .map((opt) => Number(opt.value))
    .filter((id) => Number.isFinite(id));
}
function renderAdminDefaultHouseOptions(selectedAvailableIds = [], selectedDefaultId = "") {
  const selectEl = byId("adminDefaultHouse");
  if (!selectEl) return;
  const houses = getActiveAvailableHouses(selectedAvailableIds);
  selectEl.innerHTML = optionList(houses, "不选择");
  const selected = String(selectedDefaultId || "");
  const hit = houses.some((h) => String(h.id) === selected);
  selectEl.value = hit ? selected : "";
}

function setAdminAvailableHouseIds(ids = [], keepDefaultValue = "") {
  const selectEl = byId("adminAvailableHouses");
  if (!selectEl) return;
  const idSet = new Set((ids || []).map((x) => String(x)));
  Array.from(selectEl.options).forEach((opt) => {
    opt.selected = idSet.has(String(opt.value));
  });
  renderAdminAvailableHousePicker(ids);
  renderAdminDefaultHouseOptions(ids, keepDefaultValue);
}

function renderAdminAvailableHousePicker(selectedIds = []) {
  const wrapper = byId("adminAvailableHousePicker");
  const toggle = byId("adminAvailableHouseToggle");
  const summary = byId("adminAvailableSummary");
  const chips = byId("adminAvailableChips");
  const list = byId("adminAvailableList");
  const allToggle = byId("adminAvailableAll");
  if (!wrapper || !summary || !chips || !list) return;

  const activeHouses = state.houses.filter((h) => h.is_active);
  const idSet = new Set((selectedIds || []).map((x) => Number(x)));
  const selectedHouses = activeHouses.filter((h) => idSet.has(Number(h.id)));
  const selectedNames = selectedHouses.map((h) => h.name);

  const preview = selectedHouses.slice(0, 2).map((h) => h.name).join("、");
  summary.textContent = selectedHouses.length ? `${preview}${selectedHouses.length > 2 ? ` 等${selectedHouses.length}个` : ""}` : "请选择可用房屋";
  if (toggle) toggle.title = selectedNames.length ? `已选房屋：${selectedNames.join("、")}` : "请选择可用房屋";
  chips.innerHTML = "";
  list.innerHTML = activeHouses
    .map(
      (h) =>
        `<label class="picker-option"><input type="checkbox" value="${h.id}" ${idSet.has(Number(h.id)) ? "checked" : ""} />${escapeHtml(h.name)}</label>`
    )
    .join("");

  if (allToggle) {
    allToggle.checked = activeHouses.length > 0 && selectedHouses.length === activeHouses.length;
    allToggle.indeterminate = selectedHouses.length > 0 && selectedHouses.length < activeHouses.length;
  }
}

function closeUserMenu() {
  userMenu.classList.add("hidden");
}

function positionUserMenu() {
  const rect = currentUserBtn.getBoundingClientRect();
  const width = userMenu.offsetWidth || 108;
  const left = Math.max(8, rect.right - width);
  userMenu.style.left = `${Math.round(left)}px`;
  userMenu.style.top = `${Math.round(rect.bottom + 8)}px`;
}

function openUserMenu() {
  userMenu.classList.remove("hidden");
  positionUserMenu();
}

function resetAuthView() {
  authSection.classList.remove("hidden");
  mainSection.classList.add("hidden");
  userMenuWrap.classList.add("hidden");
  closeUserMenu();
  currentUser.textContent = "未登录";
  switchAuthPage("login");
}

function applyRoleView() {
  const isAdmin = state.me?.role === "admin";
  const allowed = isAdmin
    ? new Set(["items", "locations", "categories", "tags", "users", "data", "profile"])
    : new Set(["items", "profile"]);
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("hidden", !allowed.has(tab.dataset.tab)));
  if (!allowed.has(pathToTab())) window.location.href = "/items";
}

function clearPendingFiles() {
  state.pendingFiles.forEach((x) => URL.revokeObjectURL(x.previewUrl));
  state.pendingFiles = [];
  byId("itemFiles").value = "";
  renderPendingFiles();
}

function buildTagSuggestionOptions(keyword = "", selectedTags = []) {
  const normalized = String(keyword || "").trim().toLowerCase();
  const selected = new Set((selectedTags || []).map((x) => String(x.name || "").toLowerCase()));
  return state.tags
    .filter((t) => t.is_active)
    .filter((t) => !selected.has(String(t.name || "").toLowerCase()))
    .filter((t) => !normalized || String(t.name || "").toLowerCase().includes(normalized))
    .slice(0, 10)
    .map((t) => `<option value="${escapeHtml(t.name)}"></option>`)
    .join("");
}

function refreshCreateTagSuggestions() {
  if (!itemTagInput || !itemTagOptions) return;
  itemTagOptions.innerHTML = buildTagSuggestionOptions(itemTagInput.value, state.selectedItemTags);
}

function refreshEditTagSuggestions() {
  if (!itemEditTagInput || !itemEditTagOptions) return;
  itemEditTagOptions.innerHTML = buildTagSuggestionOptions(itemEditTagInput.value, state.selectedEditItemTags);
}

function renderTagOptions() {
  refreshCreateTagSuggestions();
  refreshEditTagSuggestions();
  const searchTagOptions = byId("searchTagOptions");
  if (searchTagOptions) {
    const options = state.tags
      .filter((t) => t.is_active)
      .map((t) => `<option value="${escapeHtml(t.name)}"></option>`)
      .join("");
    searchTagOptions.innerHTML = options;
  }
}

function renderItemTagChips() {
  itemTagChips.innerHTML = state.selectedItemTags
    .map(
      (tag, index) =>
        `<span class="tag-chip">${escapeHtml(tag.name)}<button type="button" class="trash-btn" data-index="${index}" aria-label="删除标签"></button></span>`
    )
    .join("");
  refreshCreateTagSuggestions();
}

function renderEditItemTagChips() {
  if (!itemEditTagChips) return;
  itemEditTagChips.innerHTML = state.selectedEditItemTags
    .map(
      (tag, index) =>
        `<span class="tag-chip">${escapeHtml(tag.name)}<button type="button" class="trash-btn" data-index="${index}" aria-label="删除标签"></button></span>`
    )
    .join("");
  refreshEditTagSuggestions();
}

function addItemTag(raw) {
  const name = String(raw || "").trim();
  if (!name) return;
  const key = name.toLowerCase();
  if (state.selectedItemTags.some((x) => x.name.toLowerCase() === key)) return;
  if (state.selectedItemTags.length >= 50) {
    toast("最多选择 50 个标签");
    return;
  }
  const disabledHit = state.tags.find((x) => !x.is_active && x.name.toLowerCase() === key);
  if (disabledHit) {
    toast(`标签“${disabledHit.name}”已停用，不能使用`);
    return;
  }
  const found = state.tags.find((x) => x.is_active && x.name.toLowerCase() === key);
  state.selectedItemTags.push({
    id: found ? found.id : null,
    name: found ? found.name : name,
    isNew: !found,
  });
  renderItemTagChips();
}

function addEditItemTag(raw) {
  const name = String(raw || "").trim();
  if (!name) return;
  const key = name.toLowerCase();
  if (state.selectedEditItemTags.some((x) => x.name.toLowerCase() === key)) return;
  if (state.selectedEditItemTags.length >= 50) {
    toast("最多选择 50 个标签");
    return;
  }
  const disabledHit = state.tags.find((x) => !x.is_active && x.name.toLowerCase() === key);
  if (disabledHit) {
    toast(`标签“${disabledHit.name}”已停用，不能使用`);
    return;
  }
  const found = state.tags.find((x) => x.is_active && x.name.toLowerCase() === key);
  state.selectedEditItemTags.push({
    id: found ? found.id : null,
    name: found ? found.name : name,
    isNew: !found,
  });
  renderEditItemTagChips();
}

function addTagsFromInput(raw) {
  String(raw || "")
    .split(/[,\n，；;]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .forEach(addItemTag);
}

function bindImagePreview() {
  document.querySelectorAll(".thumb").forEach((node) => {
    node.onclick = () => {
      openImagePreview(node.dataset.fullUrl || node.src, node.alt || "图片预览");
    };
  });
}

function getEditExistingImageCount() {
  const itemId = Number(byId("itemForm").elements.id.value || 0);
  const item = state.items.find((x) => x.id === itemId);
  return item ? item.images.length : 0;
}

function renderPendingFiles() {
  byId("selectedFilesCount").textContent = `已选 ${state.pendingFiles.length} 张新图片`;
  const box = byId("pendingImagePreview");
  box.innerHTML = state.pendingFiles
    .map(
      (it, i) => `<div class="thumb-card">
      <img class="thumb thumb-43" src="${it.previewUrl}" alt="待上传图片" />
      <button class="thumb-delete" type="button" data-index="${i}" aria-label="删除图片"></button>
    </div>`
    )
    .join("");
  box.onclick = (e) => {
    const btn = e.target.closest("button[data-index]");
    if (!btn) return;
    const index = Number(btn.dataset.index);
    URL.revokeObjectURL(state.pendingFiles[index].previewUrl);
    state.pendingFiles.splice(index, 1);
    renderPendingFiles();
  };
  bindImagePreview();
}

async function handleItemFileChange(e) {
  const files = [...(e.target.files || [])];
  const remain = MAX_IMAGES_PER_ITEM - getEditExistingImageCount() - state.pendingFiles.length;
  if (remain <= 0) {
    toast("图片最多 9 张");
    e.target.value = "";
    return;
  }
  const selected = files.slice(0, remain);
  try {
    const compressed = await compressFilesForUpload(selected);
    compressed.forEach((f) => state.pendingFiles.push({ file: f, previewUrl: URL.createObjectURL(f) }));
    if (files.length > remain) toast(`最多上传 ${MAX_IMAGES_PER_ITEM} 张图片，已忽略超出部分`);
  } catch (err) {
    toast(err.message || "图片压缩失败");
  }
  e.target.value = "";
  renderPendingFiles();
}

function renderEditPendingFiles() {
  const countEl = byId("itemEditFilesCount");
  const box = byId("itemEditPendingPreview");
  if (!countEl || !box) return;
  countEl.textContent = `已选 ${state.editPendingFiles.length} 张新图片`;
  box.innerHTML = state.editPendingFiles
    .map(
      (it, i) => `<div class="thumb-card">
      <img class="thumb thumb-43" src="${it.previewUrl}" alt="待上传图片" />
      <button class="thumb-delete" type="button" data-index="${i}" aria-label="删除图片"></button>
    </div>`
    )
    .join("");
  box.onclick = (e) => {
    const btn = e.target.closest("button[data-index]");
    if (!btn) return;
    const index = Number(btn.dataset.index);
    URL.revokeObjectURL(state.editPendingFiles[index].previewUrl);
    state.editPendingFiles.splice(index, 1);
    renderEditPendingFiles();
  };
  bindImagePreview();
}

function clearEditPendingFiles() {
  state.editPendingFiles.forEach((x) => URL.revokeObjectURL(x.previewUrl));
  state.editPendingFiles = [];
  if (byId("itemEditFiles")) byId("itemEditFiles").value = "";
  renderEditPendingFiles();
}

async function handleEditItemFileChange(e) {
  const files = [...(e.target.files || [])];
  const currentCount = byId("itemEditCurrentImages")?.querySelectorAll("img.thumb").length || 0;
  const remain = MAX_IMAGES_PER_ITEM - currentCount - state.editPendingFiles.length;
  if (remain <= 0) {
    toast("图片最多 9 张");
    e.target.value = "";
    return;
  }
  const selected = files.slice(0, remain);
  try {
    const compressed = await compressFilesForUpload(selected);
    compressed.forEach((f) => state.editPendingFiles.push({ file: f, previewUrl: URL.createObjectURL(f) }));
    if (files.length > remain) toast(`最多上传 ${MAX_IMAGES_PER_ITEM} 张图片，已忽略超出部分`);
  } catch (err) {
    toast(err.message || "图片压缩失败");
  }
  e.target.value = "";
  renderEditPendingFiles();
}

function confirmDeleteModal({ title, summary, details }) {
  return new Promise((resolve) => {
    confirmTitle.textContent = title;
    confirmSummary.textContent = summary;
    confirmDetails.innerHTML = details.map((d) => `<div>${escapeHtml(d)}</div>`).join("");

    const onCancel = () => {
      cleanup();
      confirmDialog.close();
      resolve(false);
    };
    const onOk = () => {
      cleanup();
      confirmDialog.close();
      resolve(true);
    };
    const onClose = () => {
      cleanup();
      resolve(false);
    };
    const cleanup = () => {
      confirmCancelBtn.removeEventListener("click", onCancel);
      confirmOkBtn.removeEventListener("click", onOk);
      confirmDialog.removeEventListener("close", onClose);
    };

    confirmCancelBtn.addEventListener("click", onCancel);
    confirmOkBtn.addEventListener("click", onOk);
    confirmDialog.addEventListener("close", onClose);
    confirmDialog.showModal();
  });
}

function confirmCreateItemModal({ payload, imageCount, duplicateName }) {
  return new Promise((resolve) => {
    confirmTitle.textContent = "确认新增物品";
    confirmSummary.textContent = "请确认以下信息，确认后将执行新增。";
    const tagsText = [
      ...(payload.tag_ids || []).map((id) => {
        const hit = state.tags.find((x) => Number(x.id) === Number(id));
        return hit?.name || `ID:${id}`;
      }),
      ...(payload.tag_names || []),
    ];
    const roomName = state.rooms.find((x) => Number(x.id) === Number(payload.room_id))?.name || "-";
    const houseName = state.houses.find((x) => Number(x.id) === Number(payload.house_id))?.name || "-";
    const categoryName = state.categories.find((x) => Number(x.id) === Number(payload.category_id))?.name || "-";
    const duplicateHtml = duplicateName
      ? `<div class="item-name-duplicate-warning">警告：存在同名物品“${escapeHtml(duplicateName)}”。</div>`
      : "";
    confirmDetails.innerHTML = `${duplicateHtml}
      <div>名称：${escapeHtml(payload.name || "-")}</div>
      <div>品牌：${escapeHtml(payload.brand || "-")}</div>
      <div>数量：${payload.quantity}</div>
      <div>分类：${escapeHtml(categoryName)}</div>
      <div>房屋：${escapeHtml(houseName)}</div>
      <div>房间：${escapeHtml(roomName)}</div>
      <div>具体位置：${escapeHtml(payload.location_detail || "-")}</div>
      <div>标签：${escapeHtml(tagsText.join("、") || "-")}</div>
      <div>新上传图片：${imageCount} 张</div>`;

    const onCancel = () => {
      cleanup();
      confirmDialog.close();
      resolve(false);
    };
    const onOk = () => {
      cleanup();
      confirmDialog.close();
      resolve(true);
    };
    const onClose = () => {
      cleanup();
      resolve(false);
    };
    const cleanup = () => {
      confirmCancelBtn.removeEventListener("click", onCancel);
      confirmOkBtn.removeEventListener("click", onOk);
      confirmDialog.removeEventListener("close", onClose);
    };

    confirmCancelBtn.addEventListener("click", onCancel);
    confirmOkBtn.addEventListener("click", onOk);
    confirmDialog.addEventListener("close", onClose);
    confirmDialog.showModal();
  });
}

function renderSimpleList(containerId, rows, textFn, actions) {
  const el = byId(containerId);
  if (!rows.length) {
    el.innerHTML = "<p>暂无数据</p>";
    return;
  }
  el.innerHTML = rows
    .map((r) => {
      const html = actions
        .map((a) => `<button class="${[a.ghost ? "ghost" : "", a.danger ? "danger" : ""].join(" ").trim()}" data-id="${r.id}" data-action="${a.key}">${a.label}</button>`)
        .join("");
      return `<div class="list-row"><span>${textFn(r)}</span><span class="action-group">${html}</span></div>`;
    })
    .join("");

  el.onclick = async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const row = rows.find((x) => x.id === Number(btn.dataset.id));
    const action = actions.find((x) => x.key === btn.dataset.action);
    if (!row || !action) return;
    await action.handler(row);
  };
}

function renderRoomTree() {
  const el = byId("roomsTreeContainer");
  const groups = state.houses
    .map((h) => ({ house: h, rooms: state.rooms.filter((r) => r.house_id === h.id) }))
    .filter((x) => x.rooms.length > 0);
  if (!groups.length) {
    el.innerHTML = "<p>暂无房间</p>";
    return;
  }
  el.innerHTML = groups
    .map((g) => {
      const rows = g.rooms
        .sort((a, b) => (Number(a.sort_order || 0) - Number(b.sort_order || 0)) || (a.id - b.id))
        .map((room) => {
          if (state.roomInlineEdit === room.id) {
            return `<tr>
              <td><input id="roomInlineOrder" class="inline-input-order" type="number" min="0" value="${Number(room.sort_order || 0)}" /></td>
              <td><input id="roomInlineName" class="inline-input-name" value="${escapeHtml(room.name)}" /></td>
              <td>${room.is_active ? "启用" : "停用"}</td>
              <td>
                <span class="inline-editing">编辑中...</span>
                <button class="ghost" data-id="${room.id}" data-action="confirm">确定</button>
                <button class="ghost" data-id="${room.id}" data-action="cancel">取消</button>
              </td>
            </tr>`;
          }
          return `<tr>
            <td>${Number(room.sort_order || 0)}</td>
            <td>${escapeHtml(room.name)}</td>
            <td>${room.is_active ? "启用" : "停用"}</td>
            <td>
              <button class="ghost" data-id="${room.id}" data-action="edit">编辑</button>
              <button data-id="${room.id}" data-action="toggle">${room.is_active ? "停用" : "启用"}</button>
              <button class="danger" data-id="${room.id}" data-action="delete">删除</button>
            </td>
          </tr>`;
        })
        .join("");
      return `<details class="room-tree-house" open>
        <summary>${escapeHtml(g.house.name)}</summary>
        <div class="room-table-wrap">
          <table class="simple-table room-simple-table">
            <thead><tr><th>序号</th><th>房间名称</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </details>`;
    })
    .join("");

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  el.onclick = async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const room = state.rooms.find((r) => r.id === Number(btn.dataset.id));
    if (!room) return;
    if (btn.dataset.action === "edit") {
      state.roomInlineEdit = room.id;
      renderRoomTree();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.roomInlineEdit = null;
      renderRoomTree();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const name = byId("roomInlineName")?.value?.trim();
      const sortOrder = Number(byId("roomInlineOrder")?.value || 0);
      if (!name) {
        toast("房间名称不能为空");
        return;
      }
      await api(`/api/rooms/${room.id}`, {
        method: "PUT",
        body: JSON.stringify({ house_id: room.house_id, name, sort_order: Math.max(0, sortOrder) }),
      });
      state.roomInlineEdit = null;
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/rooms/${room.id}/${room.is_active ? "disable" : "enable"}`, { method: "POST" });
      await refreshAll();
      return;
    }
    const ok = await confirmDeleteModal({
      title: "删除房间",
      summary: "确认删除该房间吗？",
      details: [`房间：${room.name}`, `状态：${room.is_active ? "启用" : "停用"}`],
    });
    if (!ok) return;
    await api(`/api/rooms/${room.id}`, { method: "DELETE" });
    if (state.roomInlineEdit === room.id) state.roomInlineEdit = null;
    await refreshAll();
  };
}

function renderCategoriesInline() {
  const el = byId("categoriesContainer");
  if (!state.categories.length) {
    el.innerHTML = "<p>暂无分类</p>";
    return;
  }
  el.innerHTML = state.categories
    .map((x) => {
      if (state.categoryInlineEdit === x.id) {
        return `<div class="list-row">
          <span class="action-group">
            <input id="categoryInlineOrder" type="number" min="0" value="${x.sort_order || 0}" style="width:96px" />
            <input id="categoryInlineName" value="${escapeHtml(x.name)}" style="width:220px" />
            <span style="color:#f59e0b">编辑中...</span>
          </span>
          <span class="action-group">
            <button class="ghost" data-action="confirm" data-id="${x.id}">确定</button>
            <button class="ghost" data-action="cancel" data-id="${x.id}">取消</button>
          </span>
        </div>`;
      }
      return `<div class="list-row">
        <span>[${x.sort_order || 0}] ${escapeHtml(x.name)}（${x.is_active ? "启用" : "停用"}）</span>
        <span class="action-group">
          <button class="ghost" data-action="edit" data-id="${x.id}">编辑</button>
          <button data-action="toggle" data-id="${x.id}">${x.is_active ? "停用" : "启用"}</button>
          <button class="danger" data-action="delete" data-id="${x.id}">删除</button>
        </span>
      </div>`;
    })
    .join("");

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  el.onclick = async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const row = state.categories.find((x) => x.id === id);
    if (!row) return;
    if (btn.dataset.action === "edit") {
      state.categoryInlineEdit = id;
      renderCategoriesInline();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.categoryInlineEdit = null;
      renderCategoriesInline();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const name = byId("categoryInlineName")?.value?.trim();
      const sortOrder = Number(byId("categoryInlineOrder")?.value || 0);
      if (!name) {
        toast("分类名称不能为空");
        return;
      }
      await api(`/api/categories/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name, sort_order: Math.max(0, sortOrder) }),
      });
      state.categoryInlineEdit = null;
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/categories/${id}/${row.is_active ? "disable" : "enable"}`, { method: "POST" });
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "delete") {
      const ok = await confirmDeleteModal({
        title: "删除分类",
        summary: "确认删除该分类吗？",
        details: [`分类：${row.name}`],
      });
      if (!ok) return;
      await api(`/api/categories/${id}`, { method: "DELETE" });
      if (state.categoryInlineEdit === id) state.categoryInlineEdit = null;
      await refreshAll();
    }
  };
}

function renderCategoriesGrid() {
  const el = byId("categoriesContainer");
  const pager = byId("categoriesPagination");
  const keyword = (state.categoryKeyword || "").trim().toLowerCase();
  const status = state.categoryStatus || "";
  const rows = state.categories.filter((x) => {
    if (keyword && !String(x.name || "").toLowerCase().includes(keyword)) return false;
    if (status === "enabled" && !x.is_active) return false;
    if (status === "disabled" && x.is_active) return false;
    return true;
  });

  if (!rows.length) {
    el.innerHTML = "<p>暂无分类</p>";
    if (pager) pager.innerHTML = "";
    return;
  }

  const pageSize = state.categoryPageSize || 10;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.categoryPage = Math.min(Math.max(1, state.categoryPage || 1), totalPages);
  const start = (state.categoryPage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);

  const body = pageRows
    .map((x) => {
      if (state.categoryInlineEdit === x.id) {
        return `<tr>
          <td><input id="categoryInlineOrder" class="inline-input-order" type="number" min="0" value="${x.sort_order || 0}" /></td>
          <td><input id="categoryInlineName" class="inline-input-name" value="${escapeHtml(x.name)}" /></td>
          <td>${x.is_active ? "启用" : "停用"}</td>
          <td>
            <span class="inline-editing">编辑中...</span>
            <button class="ghost" data-action="confirm" data-id="${x.id}">确定</button>
            <button class="ghost" data-action="cancel" data-id="${x.id}">取消</button>
          </td>
        </tr>`;
      }
      return `<tr>
        <td>${x.sort_order || 0}</td>
        <td>${escapeHtml(x.name)}</td>
        <td>${x.is_active ? "启用" : "停用"}</td>
        <td>
          <button class="ghost" data-action="edit" data-id="${x.id}">编辑</button>
          <button data-action="toggle" data-id="${x.id}">${x.is_active ? "停用" : "启用"}</button>
          <button class="danger" data-action="delete" data-id="${x.id}">删除</button>
        </td>
      </tr>`;
    })
    .join("");

  el.innerHTML = `<table class="simple-table">
    <thead>
      <tr><th>序号</th><th>分类名称</th><th>状态</th><th>操作</th></tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  if (pager) {
    pager.innerHTML = `<span class="page-size-wrap">每页
        <select id="categoryPageSize" class="page-size-select">
          ${[5, 10, 20, 50].map((n) => `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}</option>`).join("")}
        </select> 条
      </span>
      <span>第 ${state.categoryPage} / ${totalPages} 页（共 ${rows.length} 条）</span>
      <button class="ghost" data-page="prev" ${state.categoryPage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="ghost" data-page="next" ${state.categoryPage >= totalPages ? "disabled" : ""}>下一页</button>`;
    pager.onclick = (e) => {
      const select = e.target.closest("#categoryPageSize");
      if (select) {
        state.categoryPageSize = Number(select.value || 10);
        state.categoryPage = 1;
        renderCategoriesGrid();
        return;
      }
      const btn = e.target.closest("button[data-page]");
      if (!btn) return;
      if (btn.dataset.page === "prev" && state.categoryPage > 1) state.categoryPage -= 1;
      if (btn.dataset.page === "next" && state.categoryPage < totalPages) state.categoryPage += 1;
      renderCategoriesGrid();
    };
  }

  el.onclick = async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const row = rows.find((x) => x.id === id);
    if (!row) return;

    if (btn.dataset.action === "edit") {
      state.categoryInlineEdit = id;
      renderCategoriesGrid();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.categoryInlineEdit = null;
      renderCategoriesGrid();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const name = byId("categoryInlineName")?.value?.trim();
      const sortOrder = Number(byId("categoryInlineOrder")?.value || 0);
      if (!name) {
        toast("分类名称不能为空");
        return;
      }
      await api(`/api/categories/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name, sort_order: Math.max(0, sortOrder) }),
      });
      state.categoryInlineEdit = null;
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/categories/${id}/${row.is_active ? "disable" : "enable"}`, { method: "POST" });
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "delete") {
      const ok = await confirmDeleteModal({
        title: "删除分类",
        summary: "确认删除该分类吗？",
        details: [`分类：${row.name}`],
      });
      if (!ok) return;
      await api(`/api/categories/${id}`, { method: "DELETE" });
      if (state.categoryInlineEdit === id) state.categoryInlineEdit = null;
      await refreshAll();
    }
  };
}

function renderHousesGrid() {
  const el = byId("housesContainer");
  const pager = byId("housesPagination");
  const keyword = (state.houseKeyword || "").trim().toLowerCase();
  const status = state.houseStatus || "";
  const rows = state.houses.filter((x) => {
    if (keyword && !String(x.name || "").toLowerCase().includes(keyword)) return false;
    if (status === "enabled" && !x.is_active) return false;
    if (status === "disabled" && x.is_active) return false;
    return true;
  });

  if (!rows.length) {
    el.innerHTML = "<p>暂无房屋</p>";
    if (pager) pager.innerHTML = "";
    return;
  }

  const pageSize = state.housePageSize || 10;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.housePage = Math.min(Math.max(1, state.housePage || 1), totalPages);
  const start = (state.housePage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);

  const body = pageRows
    .map((h) => {
      if (state.houseInlineEdit === h.id) {
        return `<tr>
          <td><input id="houseInlineOrder" class="inline-input-order" type="number" min="0" value="${Number(h.sort_order || 0)}" /></td>
          <td><input id="houseInlineName" class="inline-input-name" value="${escapeHtml(h.name)}" /></td>
          <td>${h.is_active ? "启用" : "停用"}</td>
          <td>
            <span class="inline-editing">编辑中...</span>
            <button class="ghost" data-action="confirm" data-id="${h.id}">确定</button>
            <button class="ghost" data-action="cancel" data-id="${h.id}">取消</button>
          </td>
        </tr>`;
      }
      return `<tr>
        <td>${Number(h.sort_order || 0)}</td>
        <td>${escapeHtml(h.name)}</td>
        <td>${h.is_active ? "启用" : "停用"}</td>
        <td>
          <button class="ghost" data-action="edit" data-id="${h.id}">编辑</button>
          <button data-action="toggle" data-id="${h.id}">${h.is_active ? "停用" : "启用"}</button>
          <button class="danger" data-action="delete" data-id="${h.id}">删除</button>
        </td>
      </tr>`;
    })
    .join("");

  el.innerHTML = `<table class="simple-table">
    <thead>
      <tr><th>序号</th><th>房屋名称</th><th>状态</th><th>操作</th></tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  if (pager) {
    pager.innerHTML = `<span class="page-size-wrap">每页
        <select id="housePageSize" class="page-size-select">
          ${[5, 10, 20, 50].map((n) => `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}</option>`).join("")}
        </select> 条
      </span>
      <span>第 ${state.housePage} / ${totalPages} 页（共 ${rows.length} 条）</span>
      <button class="ghost" data-page="prev" ${state.housePage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="ghost" data-page="next" ${state.housePage >= totalPages ? "disabled" : ""}>下一页</button>`;
    pager.onclick = (e) => {
      const select = e.target.closest("#housePageSize");
      if (select) {
        state.housePageSize = Number(select.value || 10);
        state.housePage = 1;
        renderHousesGrid();
        return;
      }
      const btn = e.target.closest("button[data-page]");
      if (!btn) return;
      if (btn.dataset.page === "prev" && state.housePage > 1) state.housePage -= 1;
      if (btn.dataset.page === "next" && state.housePage < totalPages) state.housePage += 1;
      renderHousesGrid();
    };
  }

  el.onclick = async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const row = state.houses.find((x) => x.id === id);
    if (!row) return;
    if (btn.dataset.action === "edit") {
      state.houseInlineEdit = id;
      renderHousesGrid();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.houseInlineEdit = null;
      renderHousesGrid();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const name = byId("houseInlineName")?.value?.trim();
      const sortOrder = Number(byId("houseInlineOrder")?.value || 0);
      if (!name) {
        toast("房屋名称不能为空");
        return;
      }
      await api(`/api/houses/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name, sort_order: Math.max(0, sortOrder) }),
      });
      state.houseInlineEdit = null;
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/houses/${id}/${row.is_active ? "disable" : "enable"}`, { method: "POST" });
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "delete") {
      const ok = await confirmDeleteModal({ title: "删除房屋", summary: "确认删除该房屋吗？", details: [`房屋：${row.name}`] });
      if (!ok) return;
      await api(`/api/houses/${id}`, { method: "DELETE" });
      if (state.houseInlineEdit === id) state.houseInlineEdit = null;
      await refreshAll();
    }
  };
}

function renderTagsGrid() {
  const el = byId("tagsContainer");
  const pager = byId("tagsPagination");
  const keyword = (state.tagKeyword || "").trim().toLowerCase();
  const status = state.tagStatus || "";
  const rows = state.tags.filter((x) => {
    if (keyword && !String(x.name || "").toLowerCase().includes(keyword)) return false;
    if (status === "enabled" && !x.is_active) return false;
    if (status === "disabled" && x.is_active) return false;
    return true;
  });

  if (!rows.length) {
    el.innerHTML = "<p>暂无标签</p>";
    if (pager) pager.innerHTML = "";
    return;
  }

  const pageSize = state.tagPageSize || 10;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.tagPage = Math.min(Math.max(1, state.tagPage || 1), totalPages);
  const start = (state.tagPage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);

  const body = pageRows
    .map((x) => {
      if (state.tagInlineEdit === x.id) {
        return `<tr>
          <td><input id="tagInlineName" class="inline-input-name" value="${escapeHtml(x.name)}" /></td>
          <td>${x.is_active ? "启用" : "停用"}</td>
          <td>
            <span class="inline-editing">编辑中...</span>
            <button class="ghost" data-action="confirm" data-id="${x.id}">确定</button>
            <button class="ghost" data-action="cancel" data-id="${x.id}">取消</button>
          </td>
        </tr>`;
      }
      return `<tr>
        <td>${escapeHtml(x.name)}</td>
        <td>${x.is_active ? "启用" : "停用"}</td>
        <td>
          <button class="ghost" data-action="edit" data-id="${x.id}">编辑</button>
          <button data-action="toggle" data-id="${x.id}">${x.is_active ? "停用" : "启用"}</button>
          <button class="danger" data-action="delete" data-id="${x.id}">删除</button>
        </td>
      </tr>`;
    })
    .join("");

  el.innerHTML = `<table class="simple-table">
    <thead>
      <tr><th>标签名称</th><th>状态</th><th>操作</th></tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  if (pager) {
    pager.innerHTML = `<span class="page-size-wrap">每页
        <select id="tagPageSize" class="page-size-select">
          ${[5, 10, 20, 50].map((n) => `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}</option>`).join("")}
        </select> 条
      </span>
      <span>第 ${state.tagPage} / ${totalPages} 页（共 ${rows.length} 条）</span>
      <button class="ghost" data-page="prev" ${state.tagPage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="ghost" data-page="next" ${state.tagPage >= totalPages ? "disabled" : ""}>下一页</button>`;
    pager.onclick = (e) => {
      const select = e.target.closest("#tagPageSize");
      if (select) {
        state.tagPageSize = Number(select.value || 10);
        state.tagPage = 1;
        renderTagsGrid();
        return;
      }
      const btn = e.target.closest("button[data-page]");
      if (!btn) return;
      if (btn.dataset.page === "prev" && state.tagPage > 1) state.tagPage -= 1;
      if (btn.dataset.page === "next" && state.tagPage < totalPages) state.tagPage += 1;
      renderTagsGrid();
    };
  }

  el.onclick = async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const row = rows.find((x) => x.id === id);
    if (!row) return;
    if (btn.dataset.action === "edit") {
      state.tagInlineEdit = id;
      renderTagsGrid();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.tagInlineEdit = null;
      renderTagsGrid();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const name = byId("tagInlineName")?.value?.trim();
      if (!name) {
        toast("标签名称不能为空");
        return;
      }
      await api(`/api/tags/${id}`, { method: "PUT", body: JSON.stringify({ name }) });
      state.tagInlineEdit = null;
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/tags/${id}/${row.is_active ? "disable" : "enable"}`, { method: "POST" });
      await refreshAll();
      return;
    }
    if (btn.dataset.action === "delete") {
      const ok = await confirmDeleteModal({ title: "删除标签", summary: "确认删除该标签吗？", details: [`标签：${row.name}`] });
      if (!ok) return;
      await api(`/api/tags/${id}`, { method: "DELETE" });
      if (state.tagInlineEdit === id) state.tagInlineEdit = null;
      await refreshAll();
    }
  };
}

function renderSelectors() {
  byId("searchHouse").innerHTML = optionList(state.houses, "全部房屋");
  byId("searchRoom").innerHTML = optionList([], "全部房间");
  byId("searchCategory").innerHTML = optionList(state.categories, "全部分类");
  const searchTagKeyword = byId("searchTagKeyword");
  if (searchTagKeyword) searchTagKeyword.value = state.itemTagKeyword || "";
  const activeHouses = state.houses.filter((x) => x.is_active);
  const activeCategories = state.categories.filter((x) => x.is_active);
  const activeTags = state.tags.filter((x) => x.is_active);
  byId("itemHouse").innerHTML = optionList(activeHouses, "请选择房屋");
  byId("itemCategory").innerHTML = optionList(activeCategories, "请选择分类");
  byId("itemRoom").innerHTML = `<option value="">请选择房间</option>`;
  byId("itemTags").innerHTML = activeTags.map((t) => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join("");
  if (byId("itemEditHouse")) byId("itemEditHouse").innerHTML = optionList(activeHouses, "请选择房屋");
  if (byId("itemEditCategory")) byId("itemEditCategory").innerHTML = optionList(activeCategories, "请选择分类");
  if (byId("itemEditRoom")) byId("itemEditRoom").innerHTML = `<option value="">请选择房间</option>`;
  renderTagOptions();
  byId("roomHouse").innerHTML = optionList(state.houses, "请选择房屋");
  const meAvailableIds = getCurrentUserAvailableHouseIds();
  const meAvailableActiveHouses = getActiveAvailableHouses(meAvailableIds);
  byId("profileDefaultHouse").innerHTML = optionList(meAvailableActiveHouses, "不选择");
  const adminAvailableEl = byId("adminAvailableHouses");
  if (adminAvailableEl) {
    adminAvailableEl.innerHTML = activeHouses.map((h) => `<option value="${h.id}">${escapeHtml(h.name)}</option>`).join("");
    const selectedIds = getSelectedValues(adminAvailableEl);
    renderAdminAvailableHousePicker(selectedIds);
    renderAdminDefaultHouseOptions(selectedIds);
  }
  byId("searchQ").value = state.itemKeyword || "";
  byId("searchHouse").value = state.itemHouseId || "";
  byId("searchCategory").value = state.itemCategoryId || "";
  if (searchTagKeyword && state.itemTagId) {
    const tag = state.tags.find((x) => String(x.id) === String(state.itemTagId));
    searchTagKeyword.value = tag?.name || state.itemTagKeyword || "";
  }
  filterRoomOptionsByHouse(byId("searchRoom"), state.itemHouseId || "", false, false);
  byId("searchRoom").value = state.itemRoomId || "";
  syncRoomSortOrderInput();
}
function filterRoomOptionsByHouse(targetRoomSelect, houseId, showAllWhenNoHouse = false, onlyActive = false) {
  const allRooms = onlyActive ? state.rooms.filter((r) => r.is_active) : state.rooms;
  const list = houseId ? allRooms.filter((r) => String(r.house_id) === String(houseId)) : (showAllWhenNoHouse ? allRooms : []);
  const empty = showAllWhenNoHouse ? "全部房间" : "请选择房间";
  targetRoomSelect.innerHTML = optionList(list, empty);
}

function removeEmptyOption(selectEl) {
  if (!selectEl) return;
  const emptyOpt = selectEl.querySelector('option[value=""]');
  if (emptyOpt) emptyOpt.remove();
}

function getNextSortOrderFromList(list = []) {
  const maxSort = (list || []).reduce((m, row) => Math.max(m, Number(row?.sort_order || 0)), 0);
  return maxSort + 1;
}

function getNextRoomSortOrder(houseId) {
  if (!houseId) return 0;
  const inHouse = state.rooms.filter((r) => String(r.house_id) === String(houseId));
  return getNextSortOrderFromList(inHouse);
}

function syncRoomSortOrderInput(force = false) {
  const form = byId("roomForm");
  if (!form) return;
  const isEditing = String(form.elements.id?.value || "").trim() !== "";
  if (isEditing && !force) return;
  const houseId = String(form.elements.house_id?.value || "");
  form.elements.sort_order.value = String(getNextRoomSortOrder(houseId));
}

function resetRoomForm() {
  const form = byId("roomForm");
  form.reset();
  form.elements.id.value = "";
  form.elements.name.value = "";
  byId("cancelRoomEditBtn").classList.add("hidden");
  syncRoomSortOrderInput(true);
}

function syncCreateSortOrderInputs() {
  const houseSort = byId("houseForm")?.elements?.sort_order;
  if (houseSort) houseSort.value = String(getNextSortOrderFromList(state.houses));

  const categorySort = byId("categoryForm")?.elements?.sort_order;
  if (categorySort) categorySort.value = String(getNextSortOrderFromList(state.categories));

  syncRoomSortOrderInput(true);
}

function resetHouseForm() {
  clearCrudForm("houseForm", "cancelHouseEditBtn");
  syncCreateSortOrderInputs();
}

function resetCategoryForm() {
  clearCrudForm("categoryForm", "cancelCategoryEditBtn");
  syncCreateSortOrderInputs();
}

function renderItems() {
  const box = byId("itemsContainer");
  const pager = byId("itemsPagination");
  const rows = state.items || [];
  if (!rows.length) {
    box.innerHTML = "<p>暂无物品</p>";
    if (pager) pager.innerHTML = "";
    return;
  }

  const roomNameById = new Map(state.rooms.map((r) => [Number(r.id), r.name || "-"]));
  const houseRoomText = (it) => `${it.house_name || "-"} - ${roomNameById.get(Number(it.room_id)) || "-"}`;
  const tagsText = (it) => (it.tags || []).map((x) => x.name).join("、") || "-";
  const pageSize = state.itemPageSize || 20;
  const totalPages = Math.max(1, state.itemTotalPages || 1);
  state.itemPage = Math.min(Math.max(1, state.itemPage || 1), totalPages);
  const sortLabel = (sortKey, title) => {
    if (state.itemSortKey !== sortKey) return title;
    return `${title}${state.itemSortOrder === "asc" ? " ▲" : " ▼"}`;
  };

  const body = rows
    .map((it) => {
      const houseRoom = houseRoomText(it);
      const fullTags = tagsText(it);
      const shortTags = ellipsisByChars(fullTags, 8);
      return `<tr>
        <td>${it.id}</td>
        <td>${escapeHtml(it.name || "-")}</td>
        <td>${escapeHtml(houseRoom)}</td>
        <td>${escapeHtml(it.category_name || "-")}</td>
        <td title="${escapeHtml(fullTags)}">${escapeHtml(shortTags)}</td>
        <td>${escapeHtml(formatDateOnly(it.updated_at))}</td>
        <td>
          <button class="item-mini-btn item-view-btn" data-id="${it.id}" data-action="view">查看详情</button>
          <button class="item-mini-btn item-photo-btn" data-id="${it.id}" data-action="photo">查看照片</button>
          <button class="ghost item-mini-btn" data-id="${it.id}" data-action="edit">编辑</button>
          <button class="danger item-mini-btn" data-id="${it.id}" data-action="delete">删除</button>
        </td>
      </tr>`;
    })
    .join("");

  box.innerHTML = `<table class="simple-table item-list-table">
    <thead>
      <tr>
        <th data-sort="id">${sortLabel("id", "ID")}</th>
        <th data-sort="name">${sortLabel("name", "名称")}</th>
        <th data-sort="house_room">${sortLabel("house_room", "房屋-房间")}</th>
        <th data-sort="category">${sortLabel("category", "分类")}</th>
        <th data-sort="tags">${sortLabel("tags", "标签")}</th>
        <th data-sort="updated_at">${sortLabel("updated_at", "修改时间")}</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;

  if (pager) {
    pager.innerHTML = `<span class="page-size-wrap">每页
        <select id="itemPageSize" class="page-size-select">
          ${[20, 50, 100].map((n) => `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}</option>`).join("")}
        </select>
      条</span>
      <span>第 ${state.itemPage} / ${totalPages} 页（共 ${state.itemTotal} 条）</span>
      <button class="ghost" data-page="prev" ${state.itemPage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="ghost" data-page="next" ${state.itemPage >= totalPages ? "disabled" : ""}>下一页</button>`;
    pager.onchange = async (e) => {
      const select = e.target.closest("#itemPageSize");
      if (!select) return;
      state.itemPageSize = Number(select.value || 20);
      state.itemPage = 1;
      await loadItems();
    };
    pager.onclick = async (e) => {
      const btn = e.target.closest("button[data-page]");
      if (!btn) return;
      if (btn.dataset.page === "prev" && state.itemPage > 1) state.itemPage -= 1;
      if (btn.dataset.page === "next" && state.itemPage < totalPages) state.itemPage += 1;
      await loadItems();
    };
  }

  box.onclick = async (e) => {
    const th = e.target.closest("th[data-sort]");
    if (th) {
      const nextKey = th.dataset.sort;
      if (state.itemSortKey === nextKey) state.itemSortOrder = state.itemSortOrder === "asc" ? "desc" : "asc";
      else {
        state.itemSortKey = nextKey;
        state.itemSortOrder = nextKey === "updated_at" ? "desc" : "asc";
      }
      state.itemPage = 1;
      await loadItems();
      return;
    }

    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const item = state.items.find((x) => x.id === Number(btn.dataset.id));
    if (!item) return;

    if (btn.dataset.action === "view") {
      openItemDetailDialog(item);
      return;
    }
    if (btn.dataset.action === "photo") {
      openItemPhotosDialog(item);
      return;
    }
    if (btn.dataset.action === "edit") {
      openItemEditDialog(item);
      return;
    }

    const roomName = state.rooms.find((x) => Number(x.id) === Number(item.room_id))?.name || "-";
    const ok = await confirmDeleteModal({
      title: "删除物品",
      summary: "请确认是否删除以下物品：",
      details: [
        `名称：${item.name || "-"}`,
        `品牌：${item.brand || "-"}`,
        `数量：${item.quantity}`,
        `分类：${item.category_name || "-"}`,
        `房屋：${item.house_name || "-"}`,
        `房间：${roomName}`,
        `具体位置：${item.location_detail || "-"}`,
      ],
    });
    if (!ok) return;
    await api(`/api/items/${item.id}`, { method: "DELETE" });
    await loadItems();
  };
}

function openItemDetailDialog(item) {
  if (!itemDetailDialog) return;
  const roomName = state.rooms.find((x) => Number(x.id) === Number(item.room_id))?.name || "-";
  const photoCount = (item.images || []).length;
  byId("itemDetailContent").innerHTML = `
    <table class="detail-grid-table">
      <tbody>
        <tr><th>名称</th><td>${escapeHtml(item.name || "-")}</td></tr>
        <tr><th>品牌</th><td>${escapeHtml(item.brand || "-")}</td></tr>
        <tr><th>数量</th><td>${item.quantity}</td></tr>
        <tr><th>分类</th><td>${escapeHtml(item.category_name || "-")}</td></tr>
        <tr><th>房屋</th><td>${escapeHtml(item.house_name || "-")}</td></tr>
        <tr><th>房间</th><td>${escapeHtml(roomName)}</td></tr>
        <tr><th>具体位置</th><td>${escapeHtml(item.location_detail || "-")}</td></tr>
        <tr><th>标签</th><td>${escapeHtml((item.tags || []).map((x) => x.name).join("、") || "-")}</td></tr>
        <tr><th>照片数量</th><td>${photoCount}</td></tr>
        <tr><th>录入用户</th><td>${escapeHtml(item.owner_display_name || item.owner_username || "-")}</td></tr>
        <tr><th>录入日期</th><td>${escapeHtml(formatDateTime(item.created_at))}</td></tr>
        <tr><th>最后修改</th><td>${escapeHtml(formatDateTime(item.updated_at))}</td></tr>
      </tbody>
    </table>`;
  itemDetailDialog.showModal();
}

function openItemPhotosDialog(item) {
  if (!itemPhotosDialog) return;
  const box = byId("itemPhotosContent");
  const list = item.images || [];
  if (!list.length) {
    box.innerHTML = "<p>暂无照片</p>";
  } else {
    box.innerHTML = list
      .map(
        (img) => `<div class="photo-thumb-card">
          <button type="button" class="photo-thumb-btn" data-full-url="${escapeHtml(img.url)}" data-alt="${escapeHtml(item.name || "图片")}">
            <img class="thumb thumb-43" src="${img.url}" alt="${escapeHtml(item.name || "图片")}" data-full-url="${escapeHtml(img.url)}" />
          </button>
          <div class="photo-meta">上传时间：\n${escapeHtml(formatDateTime(img.created_at, true))}</div>
        </div>`
      )
      .join("");
    box.querySelectorAll(".photo-thumb-btn").forEach((btn) => {
      const parentCard = btn.closest(".photo-thumb-card");
      const timeText = parentCard?.querySelector(".photo-meta")?.textContent?.replace(/\s+/g, " ").trim() || "";
      btn.onclick = () => openImagePreview(btn.dataset.fullUrl, btn.dataset.alt || "图片预览", `${btn.dataset.alt || "图片"}  ${timeText}`);
    });
  }
  itemPhotosDialog.showModal();
}

function renderEditCurrentImages(item) {
  const box = byId("itemEditCurrentImages");
  if (!box) return;
  const removed = new Set(state.editRemovedImageIds.map((x) => Number(x)));
  const list = (item.images || []).filter((img) => !removed.has(Number(img.id)));
  box.innerHTML = list
    .map(
      (img) => `<div class="thumb-card" data-image-id="${img.id}">
        <img class="thumb" src="${img.url}" alt="现有图片" data-full-url="${img.url}" />
        <button type="button" class="thumb-delete old-image-delete" data-image-id="${img.id}" aria-label="删除图片"></button>
      </div>`
    )
    .join("");
  box.onclick = (e) => {
    const delBtn = e.target.closest(".old-image-delete[data-image-id]");
    if (!delBtn) return;
    const imageId = Number(delBtn.dataset.imageId);
    if (!imageId) return;
    if (!state.editRemovedImageIds.includes(imageId)) state.editRemovedImageIds.push(imageId);
    delBtn.closest(".thumb-card")?.remove();
  };
}

function openItemEditDialog(item) {
  if (!itemEditDialog) return;
  const form = byId("itemEditForm");
  form.reset();
  form.elements.id.value = item.id;
  form.elements.name.value = item.name || "";
  form.elements.brand.value = item.brand || "";
  form.elements.quantity.value = item.quantity || 1;
  form.elements.location_detail.value = item.location_detail || "";

  byId("itemEditHouse").value = item.house_id || "";
  filterRoomOptionsByHouse(byId("itemEditRoom"), byId("itemEditHouse").value, false, true);
  if (byId("itemEditHouse").value) {
    removeEmptyOption(byId("itemEditHouse"));
    removeEmptyOption(byId("itemEditRoom"));
  }
  byId("itemEditRoom").value = item.room_id || "";
  byId("itemEditCategory").value = item.category_id || "";

  state.selectedEditItemTags = (item.tags || [])
    .filter((t) => state.tags.some((x) => x.is_active && Number(x.id) === Number(t.id)))
    .map((t) => ({ id: t.id, name: t.name, isNew: false }));
  renderEditItemTagChips();

  state.editRemovedImageIds = [];
  renderEditCurrentImages(item);
  clearEditPendingFiles();
  bindImagePreview();
  itemEditDialog.showModal();
}

function clearItemForm() {
  const form = byId("itemForm");
  form.reset();
  form.elements.id.value = "";
  form.elements.quantity.value = "1";
  byId("cancelEditBtn").classList.add("hidden");
  byId("editImages").innerHTML = "";
  clearPendingFiles();
  state.selectedItemTags = [];
  renderItemTagChips();

  form.elements.house_id.value = "";
  filterRoomOptionsByHouse(byId("itemRoom"), form.elements.house_id.value, false, true);
}

function fillItemForm(itemId) {
  const item = state.items.find((x) => x.id === itemId);
  if (!item) return;
  openItemEditDialog(item);
}

async function loadItems() {
  const page = Math.max(1, Number(state.itemPage) || 1);
  const pageSize = Math.max(1, Number(state.itemPageSize) || 20);
  const params = new URLSearchParams();
  if (state.itemKeyword) params.set("q", state.itemKeyword);
  if (state.itemHouseId) params.set("house_id", String(state.itemHouseId));
  if (state.itemRoomId) params.set("room_id", String(state.itemRoomId));
  if (state.itemCategoryId) params.set("category_id", String(state.itemCategoryId));
  if (state.itemTagId) params.set("tag_id", String(state.itemTagId));
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  params.set("sort_key", state.itemSortKey || "updated_at");
  params.set("sort_order", state.itemSortOrder === "asc" ? "asc" : "desc");

  const result = await api(`/api/items?${params.toString()}`);
  state.items = Array.isArray(result.items) ? result.items : [];
  state.itemTotal = Number(result.total || 0);
  state.itemTotalPages = Number(result.total_pages || 0);
  state.itemPage = Number(result.page || page);
  state.itemPageSize = Number(result.page_size || pageSize);

  if (state.itemTotal > 0 && state.itemTotalPages > 0 && state.itemPage > state.itemTotalPages) {
    state.itemPage = state.itemTotalPages;
    return loadItems();
  }

  renderItems();
}

async function loadMeta() {
  [state.houses, state.rooms, state.categories, state.tags] = await Promise.all([
    api("/api/houses"),
    api("/api/rooms"),
    api("/api/categories"),
    api("/api/tags"),
  ]);
  state.categories = [...state.categories].sort((a, b) => (Number(a.sort_order || 0) - Number(b.sort_order || 0)) || (a.id - b.id));
  renderSelectors();
  syncCreateSortOrderInputs();
  if (!byId("itemForm").elements.id.value) clearItemForm();

  renderHousesGrid();

  renderRoomTree();

  renderCategoriesGrid();

  renderTagsGrid();
}

async function loadAdminUsers() {
  if (state.me?.role !== "admin") return;
  state.users = await api("/api/admin/users");
  renderAdminUsersGrid();
}

function renderAdminUsersGrid() {
  const el = byId("adminUsersContainer");
  const pager = byId("adminUsersPagination");
  const keyword = (state.userKeyword || "").trim().toLowerCase();
  const status = state.userStatus || "";
  const role = state.userRole || "";
  const rows = state.users.filter((u) => {
    const hit = `${u.username || ""} ${u.full_name || ""}`.toLowerCase();
    if (keyword && !hit.includes(keyword)) return false;
    if (status === "enabled" && !u.is_active) return false;
    if (status === "disabled" && u.is_active) return false;
    if (role && u.role !== role) return false;
    return true;
  });

  if (!rows.length) {
    el.innerHTML = "<p>暂无用户</p>";
    if (pager) pager.innerHTML = "";
    return;
  }

  const pageSize = state.userPageSize || 10;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.userPage = Math.min(Math.max(1, state.userPage || 1), totalPages);
  const start = (state.userPage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);
  const roleText = (r) => (r === "admin" ? "管理员" : "普通用户");
  const houseNameById = new Map(state.houses.map((h) => [Number(h.id), h.name]));

  const body = pageRows
    .map((u) => {
      const availableIds = (u.available_house_ids || []).map((id) => Number(id));
      const availableNames = availableIds
        .map((id) => houseNameById.get(Number(id)) || "")
        .filter(Boolean)
        .join("、");
      if (state.userInlineEdit === u.id) {
        const activeHouses = state.houses.filter((h) => h.is_active);
        const availableOptions = activeHouses
          .map((h) => `<option value="${h.id}" ${availableIds.includes(Number(h.id)) ? "selected" : ""}>${escapeHtml(h.name)}</option>`)
          .join("");
        const defaultOptions = optionList(getActiveAvailableHouses(availableIds), "不选择");
        return `<tr>
          <td><input id="userInlineUsername" class="inline-input-name" value="${escapeHtml(u.username || "")}" /></td>
          <td><input id="userInlineName" class="inline-input-name" value="${escapeHtml(u.full_name || "")}" /></td>
          <td>
            <select id="userInlineRole" class="inline-input-name">
              <option value="user" ${u.role === "user" ? "selected" : ""}>普通用户</option>
              <option value="admin" ${u.role === "admin" ? "selected" : ""}>管理员</option>
            </select>
          </td>
          <td>${u.is_active ? "启用" : "停用"}</td>
          <td>
            <select id="userInlineAvailableHouses" class="hidden" multiple>${availableOptions}</select>
            <div id="userInlineAvailablePicker" class="multi-picker compact">
              <button type="button" id="userInlineAvailableToggle" class="multi-picker-toggle">
                <span id="userInlineAvailableSummary">请选择可用房屋</span>
                <span class="caret">▾</span>
              </button>
              <div id="userInlineAvailablePanel" class="multi-picker-panel">
                <label class="picker-option picker-option-all"><input type="checkbox" id="userInlineAvailableAll" />全选</label>
                <div id="userInlineAvailableList" class="multi-picker-list"></div>
              </div>
            </div>
          </td>
          <td>
            <select id="userInlineDefaultHouse" class="inline-input-name">
              ${defaultOptions}
            </select>
          </td>
          <td>
            <span class="inline-editing">编辑中</span>
            <button class="ghost" data-action="confirm" data-id="${u.id}">确定</button>
            <button class="ghost" data-action="cancel" data-id="${u.id}">取消</button>
          </td>
        </tr>`;
      }
      const defaultHouse = u.default_house_id ? houseNameById.get(Number(u.default_house_id)) || "-" : "-";
      return `<tr>
        <td>${escapeHtml(u.username)}</td>
        <td>${escapeHtml(u.full_name || "-")}</td>
        <td>${roleText(u.role)}</td>
        <td>${u.is_active ? "启用" : "停用"}</td>
        <td>${escapeHtml(availableNames || "-")}</td>
        <td>${escapeHtml(defaultHouse)}</td>
        <td>
          <button class="ghost" data-action="edit" data-id="${u.id}">编辑</button>
          <button data-action="toggle" data-id="${u.id}">${u.is_active ? "停用" : "启用"}</button>
          <button data-action="reset" data-id="${u.id}">重置密码</button>
          <button class="danger" data-action="delete" data-id="${u.id}">删除</button>
        </td>
      </tr>`;
    })
    .join("");

  el.innerHTML = `<table class="simple-table">
    <thead>
      <tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th><th>可用房屋</th><th>默认房屋</th><th>操作</th></tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;

  if (state.userInlineEdit) {
    const editingUser = rows.find((x) => x.id === state.userInlineEdit);
    const currentDefault = editingUser?.default_house_id ? String(editingUser.default_house_id) : "";
    const availableEl = byId("userInlineAvailableHouses");
    const defaultEl = byId("userInlineDefaultHouse");
    const inlinePicker = byId("userInlineAvailablePicker");
    const inlineToggle = byId("userInlineAvailableToggle");
    const inlineSummary = byId("userInlineAvailableSummary");
    const inlineList = byId("userInlineAvailableList");
    const inlineAll = byId("userInlineAvailableAll");
    const activeHouses = state.houses.filter((h) => h.is_active);

    const inlineSelectedIds = () => getSelectedValues(availableEl);
    const syncHiddenSelect = (ids) => {
      const idSet = new Set(ids.map((x) => String(x)));
      Array.from(availableEl.options).forEach((opt) => {
        opt.selected = idSet.has(String(opt.value));
      });
    };
    const renderInlinePicker = (ids) => {
      const idSet = new Set(ids.map((x) => Number(x)));
      const selectedHouses = activeHouses.filter((h) => idSet.has(Number(h.id)));
      const selectedNames = selectedHouses.map((h) => h.name);
      const preview = selectedHouses.slice(0, 2).map((h) => h.name).join("、");
      if (inlineSummary) {
        inlineSummary.textContent = selectedHouses.length
          ? `${preview}${selectedHouses.length > 2 ? ` 等${selectedHouses.length}个` : ""}`
          : "请选择可用房屋";
      }
      if (inlineToggle) {
        inlineToggle.title = selectedNames.length ? `已选房屋：${selectedNames.join("、")}` : "请选择可用房屋";
      }
      if (inlineList) {
        inlineList.innerHTML = activeHouses
          .map(
            (h) =>
              `<label class="picker-option"><input type="checkbox" value="${h.id}" ${idSet.has(Number(h.id)) ? "checked" : ""} />${escapeHtml(h.name)}</label>`
          )
          .join("");
      }
      if (inlineAll) {
        inlineAll.checked = activeHouses.length > 0 && selectedHouses.length === activeHouses.length;
        inlineAll.indeterminate = selectedHouses.length > 0 && selectedHouses.length < activeHouses.length;
      }
    };
    const applyInlineSelection = (ids) => {
      syncHiddenSelect(ids);
      renderInlinePicker(ids);
      syncInlineDefault();
    };

    const syncInlineDefault = () => {
      const selectedIds = getSelectedValues(availableEl);
      if (!defaultEl) return;
      defaultEl.innerHTML = optionList(getActiveAvailableHouses(selectedIds), "不选择");
      const keep = defaultEl.dataset.keep || currentDefault;
      const exists = Array.from(defaultEl.options).some((opt) => String(opt.value || "") === String(keep));
      defaultEl.value = exists ? keep : "";
      defaultEl.dataset.keep = defaultEl.value;
    };
    if (defaultEl) defaultEl.dataset.keep = currentDefault;
    if (availableEl) {
      syncInlineDefault();
      renderInlinePicker(inlineSelectedIds());
    }
    if (inlineToggle && inlinePicker) {
      inlineToggle.onclick = () => {
        inlinePicker.classList.toggle("open");
      };
    }
    if (inlineList) {
      inlineList.onchange = (e) => {
        const checkbox = e.target.closest('input[type="checkbox"]');
        if (!checkbox) return;
        const ids = Array.from(inlineList.querySelectorAll('input[type="checkbox"]:checked')).map((x) => Number(x.value));
        applyInlineSelection(ids);
      };
    }
    if (inlineAll) {
      inlineAll.onchange = (e) => {
        const ids = e.target.checked ? activeHouses.map((h) => Number(h.id)) : [];
        applyInlineSelection(ids);
      };
    }
  }

  el.querySelectorAll('button[data-action="toggle"]').forEach((btn) => {
    const txt = String(btn.textContent || "").trim();
    if (txt === "启用") btn.classList.add("success");
    else btn.classList.remove("success");
  });

  if (pager) {
    pager.innerHTML = `<span class="page-size-wrap">每页
        <select id="userPageSize" class="page-size-select">
          ${[5, 10, 20, 50].map((n) => `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}</option>`).join("")}
        </select>
      条</span>
      <span>第 ${state.userPage} / ${totalPages} 页（共 ${rows.length} 条）</span>
      <button class="ghost" data-page="prev" ${state.userPage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="ghost" data-page="next" ${state.userPage >= totalPages ? "disabled" : ""}>下一页</button>`;

    pager.onchange = (e) => {
      const select = e.target.closest("#userPageSize");
      if (!select) return;
      state.userPageSize = Number(select.value || 10);
      state.userPage = 1;
      renderAdminUsersGrid();
    };
    pager.onclick = (e) => {
      const btn = e.target.closest("button[data-page]");
      if (!btn) return;
      if (btn.dataset.page === "prev" && state.userPage > 1) state.userPage -= 1;
      if (btn.dataset.page === "next" && state.userPage < totalPages) state.userPage += 1;
      renderAdminUsersGrid();
    };
  }

  el.onclick = async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const row = rows.find((x) => x.id === id);
    if (!row) return;

    if (btn.dataset.action === "edit") {
      state.userInlineEdit = id;
      renderAdminUsersGrid();
      return;
    }
    if (btn.dataset.action === "cancel") {
      state.userInlineEdit = null;
      renderAdminUsersGrid();
      return;
    }
    if (btn.dataset.action === "confirm") {
      const username = byId("userInlineUsername")?.value?.trim() || "";
      if (username.length < 3) {
        toast("登录账号至少 3 个字符");
        return;
      }
      const availableHouseIds = getSelectedValues(byId("userInlineAvailableHouses"));
      if (!availableHouseIds.length) {
        toast("请至少选择 1 个可用房屋");
        return;
      }
      const defaultHouseValue = byId("userInlineDefaultHouse")?.value || "";
      await api(`/api/admin/users/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          username,
          full_name: byId("userInlineName")?.value?.trim() || "",
          role: byId("userInlineRole")?.value || "user",
          is_active: row.is_active,
          available_house_ids: availableHouseIds,
          default_house_id: defaultHouseValue ? Number(defaultHouseValue) : null,
        }),
      });
      state.userInlineEdit = null;
      await loadAdminUsers();
      return;
    }
    if (btn.dataset.action === "toggle") {
      await api(`/api/admin/users/${id}/${row.is_active ? "disable" : "enable"}`, { method: "POST" });
      await loadAdminUsers();
      return;
    }
    if (btn.dataset.action === "reset") {
      await api(`/api/admin/users/${id}/reset-password`, { method: "POST" });
      toast(`${row.username} 密码已重置为 123456`);
      await loadAdminUsers();
      return;
    }
    if (btn.dataset.action === "delete") {
      const ok = await confirmDeleteModal({
        title: "删除用户",
        summary: "确认删除该用户吗？",
        details: [`账号：${row.username}`, `姓名：${row.full_name || "-"}`],
      });
      if (!ok) return;
      await api(`/api/admin/users/${id}`, { method: "DELETE" });
      if (state.userInlineEdit === id) state.userInlineEdit = null;
      await loadAdminUsers();
    }
  };
}

async function refreshAll() {
  await loadMeta();
  await loadItems();
  await loadAdminUsers();
}

async function afterLogin() {
  state.me = await api("/api/me");
  currentUser.textContent = state.me.full_name || state.me.nickname || state.me.username;
  byId("profileForm").elements.nickname.value = state.me.nickname || "";
  byId("profileForm").elements.full_name.value = state.me.full_name || "";
  const profileDefaultId = String(state.me.default_house_id || "");
  const profileDefaultSelect = byId("profileForm").elements.default_house_id;
  const profileDefaultExists = Array.from(profileDefaultSelect.options).some((opt) => String(opt.value || "") === profileDefaultId);
  profileDefaultSelect.value = profileDefaultExists ? profileDefaultId : "";
  authSection.classList.add("hidden");
  mainSection.classList.remove("hidden");
  userMenuWrap.classList.remove("hidden");
  closeUserMenu();
  applyRoleView();
  switchTab(pathToTab());
  switchItemSubTab("create");
  await refreshAll();
}

function clearCrudForm(formId, cancelBtnId) {
  const form = byId(formId);
  form.reset();
  if (form.elements.id) form.elements.id.value = "";
  byId(cancelBtnId).classList.add("hidden");
}

function clearAdminUserForm() {
  const form = byId("adminUserForm");
  form.reset();
  form.elements.username.value = "";
  form.elements.full_name.value = "";
  form.elements.role.value = "user";
  setAdminAvailableHouseIds([]);
  state.userInlineEdit = null;
}
