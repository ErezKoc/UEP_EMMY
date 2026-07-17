import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { CameraIcon, ChatIcon, PawIcon, StethoscopeIcon } from "../components/ui/icons";

const FEATURES = [
  {
    icon: CameraIcon,
    title: "AI photo analysis",
    description:
      "Upload a photo of a pet and get an instant estimate of its species, breed, and age — with confidence scores for every guess.",
  },
  {
    icon: PawIcon,
    title: "Pet profiles",
    description:
      "Keep every pet's photos, details, and past AI analyses in one place, and watch their history build up over time.",
  },
  {
    icon: ChatIcon,
    title: "Community advice",
    description:
      "Ask questions, share results, and get answers from other pet owners — with verified veterinarians highlighted in every thread.",
  },
  {
    icon: StethoscopeIcon,
    title: "Vet collaboration",
    description:
      "Veterinary professionals get a dedicated space to give expert feedback and connect with pet owners who need them.",
  },
];

export default function Landing() {
  return (
    <div>
      <section className="mx-auto max-w-3xl py-16 text-center">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary-600">
          AI-assisted veterinary platform
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          Understand your pet, together with the people who care.
        </h1>
        <p className="mt-4 text-lg text-slate-600">
          Snap a photo to learn your pet's species, breed, and age — then bring your questions
          to a community of pet owners and verified veterinarians.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/analyze">
            <Button size="lg">Analyze a pet photo</Button>
          </Link>
          <Link to="/community">
            <Button variant="secondary" size="lg">
              Browse the community
            </Button>
          </Link>
        </div>
      </section>

      <section className="grid gap-6 py-8 sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <Card key={feature.title}>
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
              <feature.icon className="h-5 w-5" />
            </span>
            <h2 className="mt-3 text-lg font-semibold text-slate-800">{feature.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{feature.description}</p>
          </Card>
        ))}
      </section>

      <section className="my-8 rounded-2xl bg-primary-600 px-6 py-12 text-center">
        <h2 className="text-2xl font-bold text-white">Are you a veterinary professional?</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-primary-100">
          Join as a vet to share expert feedback, build your public profile, and collaborate
          with pet owners and fellow professionals.
        </p>
        <div className="mt-6">
          <Link to="/signup">
            <Button variant="secondary" size="lg">
              Join as a vet
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
