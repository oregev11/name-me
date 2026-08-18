// GitHub link is opt-in via VITE_GITHUB_URL -- this repo isn't pushed to a
// remote yet (see PLAN.md), so there's no real URL to hardcode. Set the env
// var once it exists and the link appears automatically; until then we
// don't ship a broken/fake link.
const GITHUB_URL = import.meta.env.VITE_GITHUB_URL as string | undefined;

export function Footer() {
  return (
    <footer className="app-footer" dir="rtl">
      <a href="/names.csv" target="_blank" rel="noreferrer">
        רשימת כל השמות (CSV)
      </a>
      {GITHUB_URL && (
        <>
          <span className="footer-sep">·</span>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">
            קוד המקור ב-GitHub
          </a>
        </>
      )}
    </footer>
  );
}
