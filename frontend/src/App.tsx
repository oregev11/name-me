import { Footer } from "./components/Footer";
import { Layout } from "./components/Layout";
import { LikedNameChips } from "./components/LikedNameChips";
import { ModelToggle } from "./components/ModelToggle";
import { NameInput } from "./components/NameInput";
import { ScatterChart } from "./components/ScatterChart";
import { SearchFilters } from "./components/SearchFilters";
import { SuggestionsList } from "./components/SuggestionsList";
import { YearRangeSlider } from "./components/YearRangeSlider";
import { useNameSearch } from "./hooks/useNameSearch";

function App() {
  const {
    likedNames,
    model,
    filters,
    yearBounds,
    result,
    loading,
    error,
    addName,
    removeName,
    setModel,
    setFilters,
  } = useNameSearch();

  return (
    <Layout>
      <ModelToggle value={model} onChange={setModel} disabled={loading} />
      <NameInput onAdd={addName} disabled={loading} />
      <LikedNameChips names={likedNames} onRemove={removeName} />
      <YearRangeSlider
        min={yearBounds.min}
        max={yearBounds.max}
        value={[
          filters.yearMin ?? yearBounds.min,
          filters.yearMax ?? yearBounds.max,
        ]}
        onChange={([yearMin, yearMax]) =>
          setFilters({
            yearMin: yearMin === yearBounds.min ? null : yearMin,
            yearMax: yearMax === yearBounds.max ? null : yearMax,
          })
        }
        disabled={loading}
      />
      <SearchFilters value={filters} onChange={setFilters} disabled={loading} />

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

      <Footer />
    </Layout>
  );
}

export default App;
