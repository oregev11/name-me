import { Layout } from "./components/Layout";
import { LikedNameChips } from "./components/LikedNameChips";
import { NameInput } from "./components/NameInput";
import { ScatterChart } from "./components/ScatterChart";
import { SuggestionsList } from "./components/SuggestionsList";
import { useNameSearch } from "./hooks/useNameSearch";

function App() {
  const { likedNames, result, loading, error, addName, removeName } =
    useNameSearch();

  return (
    <Layout>
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
          <ScatterChart liked={result.liked} suggestions={result.suggestions} />
          <SuggestionsList suggestions={result.suggestions} onAdd={addName} />
        </section>
      )}
    </Layout>
  );
}

export default App;
