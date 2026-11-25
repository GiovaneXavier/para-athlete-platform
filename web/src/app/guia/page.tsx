import type { Metadata } from "next";
import { GuideShell } from "@/components/guide/guide-shell";
import { pageByPath } from "@/lib/guide";

const page = pageByPath("/guia")!;

export const metadata: Metadata = {
  title: `${page.title} — triagem de classe esportiva`,
  description: "Guia de estudo, em português, das classes do atletismo paralímpico: grupos, classes, glossário e ilustrações.",
};

export default function GuiaPage() {
  return <GuideShell page={page} />;
}
