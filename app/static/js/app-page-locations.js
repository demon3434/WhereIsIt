byId("roomHouse").onchange = () => syncRoomSortOrderInput();

if (byId("houseKeyword")) {
  byId("houseKeyword").oninput = (e) => {
    state.houseKeyword = String(e.target.value || "");
    state.housePage = 1;
    renderHousesGrid();
  };
}
if (byId("houseStatus")) {
  byId("houseStatus").onchange = (e) => {
    state.houseStatus = String(e.target.value || "");
    state.housePage = 1;
    renderHousesGrid();
  };
}
if (byId("houseClearBtn")) {
  byId("houseClearBtn").onclick = () => {
    state.houseKeyword = "";
    state.houseStatus = "";
    state.housePage = 1;
    if (byId("houseKeyword")) byId("houseKeyword").value = "";
    if (byId("houseStatus")) byId("houseStatus").value = "";
    renderHousesGrid();
  };
}

document.querySelectorAll(".location-subtab").forEach((btn) => (btn.onclick = () => switchLocationSubTab(btn.dataset.locTab)));

byId("houseForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const id = fd.get("id");
  const body = JSON.stringify({ name: fd.get("name"), sort_order: Number(fd.get("sort_order") || 0) });
  if (id) await api(`/api/houses/${id}`, { method: "PUT", body });
  else await api("/api/houses", { method: "POST", body });
  resetHouseForm();
  await refreshAll();
};

byId("roomForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const id = fd.get("id");
    const name = String(fd.get("name") || "").trim();
    const houseId = fd.get("house_id") ? Number(fd.get("house_id")) : null;
    if (!houseId) throw new Error("请选择所属房屋");
    if (!name) throw new Error("请填写房间名称");
    const body = JSON.stringify({
      name,
      sort_order: Number(fd.get("sort_order") || 0),
      house_id: houseId,
    });
    if (id) await api(`/api/rooms/${id}`, { method: "PUT", body });
    else await api("/api/rooms", { method: "POST", body });
    resetRoomForm();
    await refreshAll();
  } catch (err) {
    toast(err.message || "新增房间失败");
  }
};


byId("cancelHouseEditBtn").onclick = resetHouseForm;
byId("cancelRoomEditBtn").onclick = resetRoomForm;
