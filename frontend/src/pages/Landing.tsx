import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { CameraIcon, ChatIcon, PawIcon, StethoscopeIcon } from "../components/ui/icons";

/*
 * Each feature says which animals it is for, on the card itself.
 *
 * The page used to promise "an instant estimate of its species" for "a pet",
 * from a model that chooses between dog and cat and nothing else — so somebody
 * with a rabbit could read this page, register, add their rabbit and only then
 * find out that two of the four things advertised do nothing for them. A scope
 * that is only discoverable after signing up is not a scope, it is a surprise.
 *
 * `scope` is a badge rather than a sentence buried in the description, because
 * the reader deciding whether to register is skimming, and the limitation is
 * the single most important thing on the card for half of them.
 */
const FEATURES = [
  {
    icon: CameraIcon,
    title: "AI photo analysis",
    scope: "Dogs and cats",
    description:
      "Upload a photo and get an estimate of the breed and age, with how strong the match was. The model was trained on dogs and cats, so it tells those two apart and does not recognise other animals.",
  },
  {
    icon: StethoscopeIcon,
    title: "Symptom checker",
    scope: "Dogs and cats",
    description:
      "Answer a few questions and get guidance on how urgently your pet should be seen, with the published veterinary source behind every answer. Those sources cover dogs and cats.",
  },
  {
    icon: PawIcon,
    title: "Pet profiles and reminders",
    scope: "Any pet",
    description:
      "Photos, details, health records and repeating reminders for vaccinations and treatments — for a rabbit or a parrot just as much as a labrador.",
  },
  {
    icon: ChatIcon,
    title: "Community and vets",
    scope: "Any pet",
    description:
      "Ask questions and get answers from other owners and verified veterinarians, and find a practice with its contact details, opening hours and out-of-hours number.",
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
          Snap a photo to estimate a dog or cat&apos;s breed and age, check symptoms against
          published veterinary guidance, and bring your questions to a community of owners and
          verified veterinarians.
        </p>

        {/*
          Above the sign-up buttons, not below them and not in a footer. The
          whole point of this line is that somebody reads it BEFORE deciding to
          register, and anything under the call to action has already lost that
          argument.
        */}
        <p className="mx-auto mt-5 max-w-xl rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <span className="font-semibold text-slate-800">Before you sign up:</span> the photo
          analysis and the symptom checker are built for <strong>dogs and cats</strong> only.
          Profiles, health records, reminders, the community and the vet directory work for any
          animal — rabbits, birds and everything else welcome.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {/*
            The requirement is ON the button, in the button.

            This page only ever renders for a signed-out visitor - a signed-in
            member gets the dashboard at "/" - so every single press of this
            button was a redirect to the login screen, from a label that gave no
            hint of it. Putting the condition in a footnote elsewhere on the
            page would not have helped: nobody reads the small print of a
            control before pressing it, and by then they are on a login form
            wondering what happened.

            It still links to /analyze rather than straight to /signup, because
            RequireAuth remembers where you were going: sign in, and you land on
            the analyzer you asked for rather than on a dashboard.
          */}
          <Link to="/analyze">
            <Button size="lg" className="flex-col gap-0 py-2.5">
              <span>Analyze a dog or cat photo</span>
              <span className="text-xs font-normal opacity-85">Free account needed</span>
            </Button>
          </Link>
          {/*
            Added as the answer to "then what CAN I do?". The symptom checker is
            deliberately public - see the route table - and it is the more
            useful thing to try first anyway if something is actually wrong with
            the animal. A page that only says no is worse than one that offers
            the door that is open.
          */}
          <Link to="/symptom-check">
            <Button variant="secondary" size="lg" className="flex-col gap-0 py-2.5">
              <span>Check symptoms</span>
              <span className="text-xs font-normal opacity-75">No account needed</span>
            </Button>
          </Link>
          <Link to="/community">
            <Button variant="ghost" size="lg">
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
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-800">{feature.title}</h2>
              {/*
                Coloured by what it means, not decoratively: amber where the
                feature is limited, slate where it is not. A reader scanning
                four cards should be able to see which two apply to their
                rabbit without reading a word.
              */}
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  feature.scope === "Any pet"
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                {feature.scope}
              </span>
            </div>
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
