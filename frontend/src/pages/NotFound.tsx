import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import { SearchIcon } from "../components/ui/icons";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl py-16">
      <EmptyState
        icon={<SearchIcon className="h-6 w-6" />}
        title="Page not found"
        description="The page you're looking for doesn't exist or may have moved."
        action={
          <Link to="/">
            <Button>Back to home</Button>
          </Link>
        }
      />
    </div>
  );
}
