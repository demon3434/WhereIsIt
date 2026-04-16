const loginForm = byId("loginForm");
if (loginForm) {
  loginForm.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const r = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: fd.get("username"), password: fd.get("password") }),
      });
      const token = r?.access_token || "";
      if (!token) throw new Error("登录返回缺少 access_token");
      setToken(token);
      if (window.location.search) {
        history.replaceState({}, "", window.location.pathname);
      }
      await afterLogin();
    } catch (err) {
      toast(err.message || "登录失败");
    }
  };
}

logoutBtn.onclick = async () => {
  closeUserMenu();
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {
    // Ignore logout request failures and still clear local auth state.
  }
  setToken("");
  window.location.href = "/login";
};

currentUserBtn.onclick = (e) => {
  e.stopPropagation();
  if (userMenu.classList.contains("hidden")) openUserMenu();
  else closeUserMenu();
};

document.addEventListener("click", (e) => {
  if (!userMenuWrap.contains(e.target)) closeUserMenu();
  const picker = byId("adminAvailableHousePicker");
  if (picker && !picker.contains(e.target)) {
    state.adminAvailableOpen = false;
    picker.classList.remove("open");
  }
  const inlinePicker = byId("userInlineAvailablePicker");
  if (inlinePicker && !inlinePicker.contains(e.target)) {
    inlinePicker.classList.remove("open");
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeUserMenu();
});

window.addEventListener("resize", () => {
  if (!userMenu.classList.contains("hidden")) positionUserMenu();
});
window.addEventListener(
  "scroll",
  () => {
    if (!userMenu.classList.contains("hidden")) positionUserMenu();
  },
  true
);

byId("goProfileBtn").onclick = () => closeUserMenu();

if (imagePreviewCloseBtn) imagePreviewCloseBtn.onclick = () => imagePreviewDialog?.close();
if (imageZoomInBtn) imageZoomInBtn.onclick = () => setPreviewScale(previewScale + 0.2);
if (imageZoomOutBtn) imageZoomOutBtn.onclick = () => setPreviewScale(previewScale - 0.2);
if (imageZoomResetBtn) imageZoomResetBtn.onclick = () => setPreviewScale(1);
if (imagePreviewDialog) {
  imagePreviewDialog.addEventListener("click", (e) => {
    if (e.target === imagePreviewDialog) imagePreviewDialog.close();
  });
}
if (imagePreviewStage) {
  imagePreviewStage.addEventListener(
    "wheel",
    (e) => {
      if (!imagePreviewDialog?.open) return;
      e.preventDefault();
      if (e.deltaY < 0) setPreviewScale(previewScale + 0.12);
      else setPreviewScale(previewScale - 0.12);
    },
    { passive: false }
  );
}

bindTopTabNavigation();

(async function init() {
  const path = window.location.pathname.toLowerCase();
  if (path === "/login") switchAuthPage("login");

  // Clear leaked credentials from URL, e.g. ?username=...&password=...
  if (window.location.search) {
    const params = new URLSearchParams(window.location.search);
    if (params.has("username") || params.has("password")) {
      history.replaceState({}, "", window.location.pathname);
    }
  }

  if (!state.token) {
    resetAuthView();
    finishBoot();
    return;
  }
  try {
    await afterLogin();
    switchLocationSubTab("house");
  } catch {
    setToken("");
    resetAuthView();
  } finally {
    finishBoot();
  }
})();
