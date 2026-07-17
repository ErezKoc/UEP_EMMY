import PlaceholderPage from "../../components/layout/PlaceholderPage";

// Member 3 (Pets): list of the current user's animals.
// Needs a /v1/animals router in the backend (the SQLAlchemy Animal model already exists).
// Suggested: grid of <Card>s, "Add pet" <Button> opening a <Modal> with the pet form,
// <EmptyState> when the user has no pets yet.
export default function PetsPage() {
  return (
    <PlaceholderPage
      title="My pets"
      owner="Member 3"
      description="Grid of the user's pets with an add/edit pet form. Each pet links to its detail page at /pets/:id."
    />
  );
}
