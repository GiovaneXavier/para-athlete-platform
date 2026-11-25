import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GuideShell } from "@/components/guide/guide-shell";
import { classParams, pageByPath } from "@/lib/guide";

export function generateStaticParams() {
  return classParams();
}

type Params = Promise<{ grupo: string; classe: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { grupo, classe } = await params;
  const page = pageByPath(`/guia/${grupo}/${classe}`);
  return { title: page ? `${page.title} — guia de classes` : "Guia de classes" };
}

export default async function ClassPage({ params }: { params: Params }) {
  const { grupo, classe } = await params;
  const page = pageByPath(`/guia/${grupo}/${classe}`);
  if (!page || page.kind !== "class") notFound();
  return <GuideShell page={page} />;
}
