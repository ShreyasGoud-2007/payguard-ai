import { createFileRoute } from "@tanstack/react-router";
import { CinematicIntro } from "@/components/payguard/CinematicIntro";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "PayGuard AI · Every payment, on the radar" }, { name: "description", content: "A command center for safer, faster accounts payable operations." }, { property: "og:title", content: "PayGuard AI · Every payment, on the radar" }, { property: "og:description", content: "A command center for safer, faster accounts payable operations." }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary_large_image" }] }),
  component: CinematicIntro,
});
