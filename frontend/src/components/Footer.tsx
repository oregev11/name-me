// GitHub link is opt-in via VITE_GITHUB_URL, defaulted to this project's
// real repo in .env.example -- kept overridable (rather than hardcoded) so
// a fork shows its own repo instead of silently linking to the original.
const GITHUB_URL = import.meta.env.VITE_GITHUB_URL as string | undefined;

// The upstream name-corpus data source (see DATA_SOURCE.md) -- a fixed
// citation, not deployment-specific, so unlike GITHUB_URL this isn't an
// env var.
const NAMES_SOURCE_URL = "https://github.com/aviezerl/babynamesIL";

export function Footer() {
  return (
    <footer className="app-footer" dir="rtl">
      <a href="/names.csv" target="_blank" rel="noreferrer">
        רשימת כל השמות (CSV)
      </a>
      <span className="footer-sep">·</span>
      <a href={NAMES_SOURCE_URL} target="_blank" rel="noreferrer">
        מקור הנתונים (babynamesIL)
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
