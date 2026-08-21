import { useState } from "react";
import { PawIcon } from "../../components/ui/icons";

type PetKind = "cat" | "dog";

const GUIDES = {
  cat: {
    label: "Cat",
    intro: "A calm home, predictable routine, and a few well-placed essentials help a new cat settle in safely.",
    sections: [
      ["Food & water", "Choose complete cat food that matches your cat's life stage.", ["Keep fresh, clean water available at all times.", "Use measured portions and ask your veterinarian how much is appropriate.", "Change foods gradually to reduce stomach upset."]],
      ["Litter box", "Place the box in a quiet, easy-to-reach location.", ["Scoop waste every day and clean the box regularly.", "A common starting point is one box per cat, plus one extra.", "Sudden litter-box avoidance can have a medical cause; contact a veterinarian."]],
      ["Home & enrichment", "Cats need safe hiding, resting, climbing, scratching, and play areas.", ["Provide a stable scratching post and interactive toys.", "Secure windows, balconies, cords, medicines, and toxic household products.", "Let a nervous cat approach you at its own pace."]],
      ["Grooming & health", "Regular observation makes changes easier to notice early.", ["Brush regularly and introduce nail care gently.", "Arrange an initial veterinary exam, vaccines, parasite control, and microchip advice.", "Never give human medicine unless a veterinarian specifically instructs you to."]],
    ],
    insights: [
      ["Lilies are an emergency", "True lilies and daylilies can cause fatal kidney injury. Even pollen on the coat or water from the vase can be dangerous; contact a veterinarian immediately after possible exposure."],
      ["Straining is not always constipation", "Repeated litter-box visits with little or no urine can mean a blocked urinary tract, especially in male cats. This is an emergency."],
      ["Bowls and litter should be separated", "Keep food and water well away from the litter box. Some cats also drink more readily when several clean water bowls are available in quiet locations."],
      ["A hiding cat may be unwell", "Cats often conceal pain or illness. A sudden change in hiding, appetite, drinking, grooming, movement, or litter-box habits deserves attention."],
      ["String toys need supervision", "Thread, ribbon, yarn, and hair ties can be swallowed and damage the intestines. Store them away after play and do not pull visible string from the mouth or rear—call a veterinarian."],
      ["Dog flea products may harm cats", "Never apply a product labeled only for dogs to a cat. Some dog parasite products contain ingredients that are highly toxic to cats."],
    ],
  },
  dog: {
    label: "Dog",
    intro: "Consistent routines, positive training, safe exercise, and preventive care build a strong start for a new dog.",
    sections: [
      ["Food & water", "Choose complete dog food suited to age, size, and health needs.", ["Keep fresh, clean water available at all times.", "Measure meals and limit treats so they remain a small part of the diet.", "Ask your veterinarian before making major diet changes."]],
      ["Training & routine", "Simple, predictable routines make a new home easier to understand.", ["Use rewards and short, positive training sessions.", "Offer frequent toilet breaks, especially for puppies.", "Introduce people, sounds, and environments gradually and safely."]],
      ["Exercise & safety", "Exercise needs vary with age, breed, size, and health.", ["Use a secure collar or harness, ID tag, and leash outdoors.", "Combine walks with play, sniffing, and mental enrichment.", "Secure medicines, chemicals, food waste, cables, gates, and balconies."]],
      ["Grooming & health", "Build gentle handling into the routine from the beginning.", ["Brush the coat and check ears, paws, teeth, and nails regularly.", "Arrange an initial veterinary exam, vaccines, parasite control, and microchip advice.", "Never give human medicine unless a veterinarian specifically instructs you to."]],
    ],
    insights: [
      ["Sugar-free can be dangerous", "Xylitol in gum, sweets, toothpaste, baked goods, and some supplements can cause dangerously low blood sugar and liver injury. Treat possible ingestion as urgent."],
      ["Grapes and raisins are not safe treats", "They can cause kidney injury in dogs, and a safe amount cannot be assumed. Contact a veterinarian after any suspected ingestion."],
      ["A wagging tail is not automatic permission", "A wag can also signal tension or high arousal. Look at the whole body and let unfamiliar dogs choose whether to approach."],
      ["Hot cars become dangerous quickly", "Shade and an open window do not make a parked car safe. On warm days, leave the dog at home when it cannot accompany you indoors."],
      ["Exercise after a large meal can be risky", "Deep-chested dogs can be vulnerable to gastric dilatation-volvulus (bloat). A swollen abdomen, unproductive retching, restlessness, or collapse needs emergency care."],
      ["A cold, wet nose does not prove health", "Nose temperature and moisture change normally. Appetite, energy, breathing, vomiting, stool, pain, and behavior are more useful warning signs."],
    ],
  },
} satisfies Record<PetKind, { label: string; intro: string; sections: [string, string, string[]][]; insights: [string, string][] }>;

function PetIcon() {
  return (
    <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-100 text-primary-700" aria-hidden>
      <PawIcon className="h-9 w-9" />
    </span>
  );
}

export default function NewOwnerGuidePage() {
  const [selected, setSelected] = useState<PetKind>("cat");
  const guide = GUIDES[selected];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary-600">Getting started</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900 sm:text-4xl">New Owner Guide</h1>
        <p className="mx-auto mt-3 max-w-2xl text-slate-600">Choose your new companion for a practical overview of everyday care, safety, and first steps.</p>
      </header>

      <div className="mx-auto grid max-w-xl grid-cols-2 gap-3" role="tablist" aria-label="Choose a pet">
        {(["cat", "dog"] as const).map((kind) => {
          const active = selected === kind;
          return <button key={kind} type="button" role="tab" aria-selected={active} onClick={() => setSelected(kind)} className={`flex items-center gap-3 rounded-2xl border p-4 text-left transition ${active ? "border-primary-500 bg-primary-50 shadow-sm ring-2 ring-primary-100" : "border-slate-200 bg-white hover:border-primary-200"}`}>
            <PetIcon />
            <span><span className="block text-lg font-bold text-slate-900">{GUIDES[kind].label}</span><span className="text-xs text-slate-500">View basic care</span></span>
          </button>;
        })}
      </div>

      <section role="tabpanel" className="space-y-5">
        <div className="rounded-2xl bg-primary-700 p-6 text-white shadow-sm">
          <p className="text-sm font-semibold text-primary-100">Your first steps with a {guide.label.toLowerCase()}</p>
          <p className="mt-2 text-lg leading-relaxed">{guide.intro}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {guide.sections.map(([title, summary, tips], index) => <article key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-700">{index + 1}</span><div><h2 className="text-lg font-bold text-slate-900">{title}</h2><p className="mt-1 text-sm text-slate-600">{summary}</p></div></div>
            <ul className="mt-4 space-y-2 pl-11 text-sm leading-relaxed text-slate-700">{tips.map((tip) => <li key={tip} className="relative before:absolute before:-left-4 before:text-primary-500 before:content-['✓']">{tip}</li>)}</ul>
          </article>)}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-primary-600">Easy to miss</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-900">Good to know as a new owner</h2>
          <p className="mt-1 text-sm text-slate-600">Less obvious facts that can prevent common mistakes and emergencies.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {guide.insights.map(([title, detail]) => <article key={title} className="rounded-2xl border border-primary-100 bg-gradient-to-br from-white to-primary-50 p-5">
            <h3 className="font-bold text-slate-900">{title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{detail}</p>
          </article>)}
        </div>
      </section>

      <aside className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950">
        <h2 className="font-bold">Important</h2>
        <p className="mt-1 leading-relaxed">This page provides general education, not diagnosis or treatment. Care needs vary by age, breed, health, and lifestyle. Arrange a veterinary visit soon after adoption. Seek urgent veterinary help for breathing difficulty, collapse, seizures, major injury, suspected poisoning, or other severe or rapidly worsening symptoms.</p>
      </aside>
    </div>
  );
}
