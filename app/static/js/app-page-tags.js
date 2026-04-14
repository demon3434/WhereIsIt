if (byId("tagKeyword")) {
  byId("tagKeyword").oninput = (e) => {
    state.tagKeyword = String(e.target.value || "");
    state.tagPage = 1;
    renderTagsGrid();
  };
}
if (byId("tagStatus")) {
  byId("tagStatus").onchange = (e) => {
    state.tagStatus = String(e.target.value || "");
    state.tagPage = 1;
    renderTagsGrid();
  };
}
if (byId("tagClearBtn")) {
  byId("tagClearBtn").onclick = () => {
    state.tagKeyword = "";
    state.tagStatus = "";
    state.tagPage = 1;
    if (byId("tagKeyword")) byId("tagKeyword").value = "";
    if (byId("tagStatus")) byId("tagStatus").value = "";
    renderTagsGrid();
  };
}

byId("tagForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = JSON.stringify({ name: String(fd.get("name") || "").trim() });
  await api("/api/tags", { method: "POST", body });
  byId("tagForm").reset();
  state.tagInlineEdit = null;
  state.tagPage = 1;
  await refreshAll();
};

