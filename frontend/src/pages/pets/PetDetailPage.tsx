import { useParams } from "react-router-dom";
import PlaceholderPage from "../../components/layout/PlaceholderPage";

// Member 3 (Pets): a single pet's profile.
// Shows photo, species/breed/age, notes — and (with Member 4) the pet's analysis history.
export default function PetDetailPage() {
  const { petId } = useParams();
  return (
    <PlaceholderPage
      title={`Pet #${petId ?? "?"}`}
      owner="Member 3"
      description="Pet profile: photo, species, breed, age, notes, and the pet's AI analysis history (analysis section by Member 4)."
    />
  );
}
