import type { SampleBrowserViewModel } from "../viewModels/sampleBrowser";

export default function SampleMetadataView({ vm }: { vm: SampleBrowserViewModel }) {
  const selected = vm.samples.find((sample) => sample.id === vm.selectedSampleId);

  if (!selected) {
    return <div className="ide-tool-empty">No sample selected.</div>;
  }

  const metadata = {
    id: selected.id,
    title: selected.title,
    description: selected.description,
    category: selected.category,
    path: selected.path,
    tags: selected.tags,
    metadata: selected.metadata,
    raw: selected.raw,
  };

  return (
    <div className="ide-artifact-state" data-sample-metadata="phase-4-5-c2-e">
      <div className="ide-section-title">Sample Metadata</div>
      <div className="ide-artifact-row">
        <span>Sample</span>
        <strong>{selected.title}</strong>
      </div>
      <div className="ide-artifact-row">
        <span>Category</span>
        <strong>{selected.category ?? "uncategorized"}</strong>
      </div>
      <pre className="ide-json-block">{JSON.stringify(metadata, null, 2)}</pre>
    </div>
  );
}
