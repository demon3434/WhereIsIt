byId("adminUserForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const availableHouseIds = getSelectedValues(byId("adminAvailableHouses"));
  if (!availableHouseIds.length) {
    toast("请至少选择 1 个可用房屋");
    return;
  }
  await api("/api/admin/users", {
    method: "POST",
    body: JSON.stringify({
      username: String(fd.get("username") || "").trim(),
      full_name: String(fd.get("full_name") || "").trim(),
      password: String(fd.get("password") || "").trim() || "123456",
      role: fd.get("role") || "user",
      is_active: true,
      available_house_ids: availableHouseIds,
      default_house_id: fd.get("default_house_id") ? Number(fd.get("default_house_id")) : null,
    }),
  });
  clearAdminUserForm();
  await loadAdminUsers();
};

if (byId("adminAvailableHouseToggle")) {
  byId("adminAvailableHouseToggle").onclick = () => {
    state.adminAvailableOpen = !state.adminAvailableOpen;
    byId("adminAvailableHousePicker")?.classList.toggle("open", state.adminAvailableOpen);
  };
}
if (byId("adminAvailableList")) {
  byId("adminAvailableList").onchange = (e) => {
    const checkbox = e.target.closest('input[type="checkbox"]');
    if (!checkbox) return;
    const checkedIds = Array.from(byId("adminAvailableList").querySelectorAll('input[type="checkbox"]:checked')).map((x) =>
      Number(x.value)
    );
    const keep = byId("adminDefaultHouse")?.value || "";
    setAdminAvailableHouseIds(checkedIds, keep);
  };
}
if (byId("adminAvailableAll")) {
  byId("adminAvailableAll").onchange = (e) => {
    const checked = Boolean(e.target.checked);
    const ids = checked ? state.houses.filter((h) => h.is_active).map((h) => Number(h.id)) : [];
    const keep = byId("adminDefaultHouse")?.value || "";
    setAdminAvailableHouseIds(ids, keep);
  };
}

if (byId("userKeyword")) {
  byId("userKeyword").oninput = (e) => {
    state.userKeyword = String(e.target.value || "");
    state.userPage = 1;
    renderAdminUsersGrid();
  };
}
if (byId("userStatus")) {
  byId("userStatus").onchange = (e) => {
    state.userStatus = String(e.target.value || "");
    state.userPage = 1;
    renderAdminUsersGrid();
  };
}
if (byId("userRole")) {
  byId("userRole").onchange = (e) => {
    state.userRole = String(e.target.value || "");
    state.userPage = 1;
    renderAdminUsersGrid();
  };
}
if (byId("userClearBtn")) {
  byId("userClearBtn").onclick = () => {
    state.userKeyword = "";
    state.userStatus = "";
    state.userRole = "";
    state.userPage = 1;
    if (byId("userKeyword")) byId("userKeyword").value = "";
    if (byId("userStatus")) byId("userStatus").value = "";
    if (byId("userRole")) byId("userRole").value = "";
    renderAdminUsersGrid();
  };
}
