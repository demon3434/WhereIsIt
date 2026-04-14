if (byId("categoryKeyword")) {
  byId("categoryKeyword").oninput = (e) => {
    state.categoryKeyword = String(e.target.value || "");
    state.categoryPage = 1;
    renderCategoriesGrid();
  };
}
if (byId("categoryStatus")) {
  byId("categoryStatus").onchange = (e) => {
    state.categoryStatus = String(e.target.value || "");
    state.categoryPage = 1;
    renderCategoriesGrid();
  };
}
if (byId("categoryClearBtn")) {
  byId("categoryClearBtn").onclick = () => {
    state.categoryKeyword = "";
    state.categoryStatus = "";
    state.categoryPage = 1;
    if (byId("categoryKeyword")) byId("categoryKeyword").value = "";
    if (byId("categoryStatus")) byId("categoryStatus").value = "";
    renderCategoriesGrid();
  };
}

byId("categoryForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = JSON.stringify({ name: fd.get("name"), sort_order: Number(fd.get("sort_order") || 0) });
  await api("/api/categories", { method: "POST", body });
  resetCategoryForm();
  state.categoryInlineEdit = null;
  state.categoryPage = 1;
  await refreshAll();
};


byId("cancelCategoryEditBtn").onclick = resetCategoryForm;
