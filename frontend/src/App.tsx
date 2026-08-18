import { Layout } from "./components/Layout";
import { LikedNameChips } from "./components/LikedNameChips";
import { ModelToggle } from "./components/ModelToggle";
import { NameInput } from "./components/NameInput";
import { ScatterChart } from "./components/ScatterChart";
import { SuggestionsList } from "./components/SuggestionsList";
import { useNameSearch } from "./hooks/useNameSearch";

function App() {
  const {
    likedNames,
    model,
    result,
    loading,
    error,
    addName,
    removeName,
    setModel,
  } = useNameSearch();

  return (
    <Layout>
      <ModelToggle value={model} onChange={setModel} disabled={loading} />
      <NameInput onAdd={addName} disabled={loading} />
      <LikedNameChips names={likedNames} onRemove={removeName} />

      {loading && (
        <p className="status">מחפש שמות דומים... (עד דקה בהפעלה ראשונה)</p>
      )}
      {error && (
        <p className="status status-error" role="alert">
          {error}
        </p>
      )}

      {result && !loading && (
        <section className="results">
          {/* Keying on `model` forces a clean remount instead of an
              interpolated transition -- switching models jumps to an
              unrelated PCA coordinate space, which is expected. */}
          <ScatterChart
            key={model}
            liked={result.liked}
            suggestions={result.suggestions}
          />
          <SuggestionsList suggestions={result.suggestions} onAdd={addName} />
        </section>
      )}
    </Layout>
  );
}

export default App;
