byId("searchHouse").onchange = async () => {
  state.itemHouseId = byId("searchHouse").value || "";
  state.itemRoomId = "";
  state.itemPage = 1;
  filterRoomOptionsByHouse(byId("searchRoom"), state.itemHouseId, false, false);
  byId("searchRoom").value = "";
  await loadItems();
};
byId("itemHouse").onchange = () => {
  const houseVal = byId("itemHouse").value;
  filterRoomOptionsByHouse(byId("itemRoom"), houseVal, false, true);
};

byId("searchBtn").onclick = async () => {
  state.itemKeyword = byId("searchQ").value.trim();
  state.itemHouseId = byId("searchHouse").value || "";
  state.itemRoomId = byId("searchRoom").value || "";
  state.itemCategoryId = byId("searchCategory").value || "";
  state.itemTagKeyword = byId("searchTagKeyword")?.value?.trim() || "";
  const tag = state.tags.find((x) => x.name.toLowerCase() === state.itemTagKeyword.toLowerCase());
  state.itemTagId = tag ? String(tag.id) : "";
  state.itemPage = 1;
  await loadItems();
};
byId("resetSearchBtn").onclick = async () => {
  state.itemKeyword = "";
  state.itemHouseId = "";
  state.itemRoomId = "";
  state.itemCategoryId = "";
  state.itemTagId = "";
  state.itemTagKeyword = "";
  state.itemPage = 1;
  ["searchQ", "searchHouse", "searchRoom", "searchCategory", "searchTagKeyword"].forEach((id) => (byId(id).value = ""));
  filterRoomOptionsByHouse(byId("searchRoom"), "", false, false);
  await loadItems();
};

itemTagInput.onkeydown = (e) => {
  if (e.key !== "Enter") return;
  e.preventDefault();
  addTagsFromInput(itemTagInput.value);
  itemTagInput.value = "";
};
itemTagInput.oninput = () => refreshCreateTagSuggestions();
itemTagInput.onfocus = () => refreshCreateTagSuggestions();
itemTagInput.onblur = () => {
  addTagsFromInput(itemTagInput.value);
  itemTagInput.value = "";
  refreshCreateTagSuggestions();
};
itemTagChips.onclick = (e) => {
  const btn = e.target.closest("button[data-index]");
  if (!btn) return;
  state.selectedItemTags.splice(Number(btn.dataset.index), 1);
  renderItemTagChips();
};

byId("itemFiles").addEventListener("change", handleItemFileChange);
byId("cancelEditBtn").onclick = clearItemForm;
if (itemEditTagInput) {
  itemEditTagInput.onkeydown = (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    addEditItemTag(itemEditTagInput.value);
    itemEditTagInput.value = "";
  };
  itemEditTagInput.oninput = () => refreshEditTagSuggestions();
  itemEditTagInput.onfocus = () => refreshEditTagSuggestions();
  itemEditTagInput.onblur = () => {
    addEditItemTag(itemEditTagInput.value);
    itemEditTagInput.value = "";
    refreshEditTagSuggestions();
  };
}
if (itemEditTagChips) {
  itemEditTagChips.onclick = (e) => {
    const btn = e.target.closest("button[data-index]");
    if (!btn) return;
    state.selectedEditItemTags.splice(Number(btn.dataset.index), 1);
    renderEditItemTagChips();
  };
}
if (byId("itemEditFiles")) byId("itemEditFiles").addEventListener("change", handleEditItemFileChange);
if (byId("itemDetailCloseBtn")) byId("itemDetailCloseBtn").onclick = () => itemDetailDialog?.close();
if (byId("itemPhotosCloseBtn")) byId("itemPhotosCloseBtn").onclick = () => itemPhotosDialog?.close();
if (byId("itemEditCancelBtn")) byId("itemEditCancelBtn").onclick = () => itemEditDialog?.close();

if (byId("itemEditHouse")) {
  byId("itemEditHouse").onchange = () => {
    const houseVal = byId("itemEditHouse").value || "";
    filterRoomOptionsByHouse(byId("itemEditRoom"), houseVal, false, true);
  };
}


document.querySelectorAll(".item-subtab").forEach((btn) => (btn.onclick = () => switchItemSubTab(btn.dataset.itemTab)));

byId("itemForm").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const fd = new FormData(f);
  try {
    const name = String(fd.get("name") || "").trim();
    if (!name) throw new Error("请填写名称");
    if (!fd.get("house_id")) throw new Error("请选择房屋");
    if (!fd.get("room_id")) throw new Error("请选择房间");
    if (!fd.get("category_id")) throw new Error("请选择分类");
    if (Number(fd.get("quantity") || 0) < 1) throw new Error("数量必须大于等于 1");
    if (!String(fd.get("location_detail") || "").trim()) throw new Error("请填写具体位置");

    const itemId = fd.get("id");
    const houseId = Number(fd.get("house_id"));
    const roomId = Number(fd.get("room_id"));
    const categoryId = Number(fd.get("category_id"));
    const houseActive = state.houses.some((x) => x.is_active && Number(x.id) === houseId);
    const roomActive = state.rooms.some((x) => x.is_active && Number(x.id) === roomId && Number(x.house_id) === houseId);
    const categoryActive = state.categories.some((x) => x.is_active && Number(x.id) === categoryId);
    if (!houseActive) throw new Error("所选房屋已停用，请重新选择");
    if (!roomActive) throw new Error("所选房间已停用或与房屋不匹配，请重新选择");
    if (!categoryActive) throw new Error("所选分类已停用，请重新选择");

    const payload = {
      name,
      brand: fd.get("brand") || "",
      quantity: Number(fd.get("quantity") || 1),
      category_id: categoryId,
      house_id: houseId,
      room_id: roomId,
      location_detail: fd.get("location_detail") || "",
      tag_ids: state.selectedItemTags.filter((x) => x.id).map((x) => Number(x.id)),
      tag_names: state.selectedItemTags.filter((x) => !x.id).map((x) => x.name),
      image_orders: state.pendingFiles.map((it, index) => ({
        file_key: it.fileKey,
        display_order: index + 1,
      })),
    };

    const duplicate = state.items.find(
      (x) => x.name && x.name.trim().toLowerCase() === name.toLowerCase() && String(x.id) !== String(itemId || "")
    );
    if (!itemId) {
      const ok = await confirmCreateItemModal({
        payload,
        imageCount: state.pendingFiles.length,
        duplicateName: duplicate ? duplicate.name : "",
      });
      if (!ok) return;
    }

    const body = new FormData();
    body.append("data", JSON.stringify(payload));
    state.pendingFiles.forEach((it) => {
      body.append("files", it.file);
      body.append("file_keys", it.fileKey);
    });
    if (itemId) await api(`/api/items/${itemId}`, { method: "PUT", body });
    else await api("/api/items", { method: "POST", body });

    clearItemForm();
    switchItemSubTab("list");
    await loadItems();
    await loadMeta();
  } catch (err) {
    toast(err.message || "保存失败");
  }
};

if (byId("itemEditForm")) {
  byId("itemEditForm").onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    try {
      const id = Number(fd.get("id") || 0);
      const name = String(fd.get("name") || "").trim();
      if (!id) throw new Error("物品ID无效");
      if (!name) throw new Error("请填写名称");
      if (!fd.get("house_id")) throw new Error("请选择房屋");
      if (!fd.get("room_id")) throw new Error("请选择房间");
      if (!fd.get("category_id")) throw new Error("请选择分类");
      if (Number(fd.get("quantity") || 0) < 1) throw new Error("数量必须大于等于 1");
      if (!String(fd.get("location_detail") || "").trim()) throw new Error("请填写具体位置");

      const payload = {
        name,
        brand: fd.get("brand") || "",
        quantity: Number(fd.get("quantity") || 1),
        category_id: Number(fd.get("category_id")),
        house_id: Number(fd.get("house_id")),
        room_id: Number(fd.get("room_id")),
        location_detail: fd.get("location_detail") || "",
        tag_ids: state.selectedEditItemTags.filter((x) => x.id).map((x) => Number(x.id)),
        tag_names: state.selectedEditItemTags.filter((x) => !x.id).map((x) => x.name),
        image_orders: state.editImageEntries.map((entry, index) => ({
          image_id: entry.kind === "existing" ? Number(entry.imageId) : null,
          file_key: entry.kind === "new" ? entry.fileKey : null,
          display_order: index + 1,
        })),
      };

      const body = new FormData();
      body.append("data", JSON.stringify(payload));
      state.editImageEntries
        .filter((entry) => entry.kind === "new")
        .forEach((entry) => {
          body.append("files", entry.file);
          body.append("file_keys", entry.fileKey);
        });
      for (const imageId of state.editRemovedImageIds) {
        await api(`/api/items/${id}/images/${imageId}`, { method: "DELETE" });
      }
      await api(`/api/items/${id}`, { method: "PUT", body });
      clearEditPendingFiles();
      state.editRemovedImageIds = [];
      itemEditDialog?.close();
      await loadItems();
      await loadMeta();
    } catch (err) {
      toast(err.message || "保存失败");
    }
  };
}
