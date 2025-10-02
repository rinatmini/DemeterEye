export function setToken(t) {
  if (t) localStorage.setItem("jwt", t);
  else localStorage.removeItem("jwt");
}
export function getToken() {
  return localStorage.getItem("jwt");
}
