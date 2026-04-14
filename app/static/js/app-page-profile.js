byId("profileForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/api/me", {
    method: "PUT",
    body: JSON.stringify({
      nickname: fd.get("nickname") || "",
      full_name: fd.get("full_name") || "",
      default_house_id: fd.get("default_house_id") ? Number(fd.get("default_house_id")) : null,
      password: fd.get("password") || null,
    }),
  });
  e.target.elements.password.value = "";
  await afterLogin();
};

