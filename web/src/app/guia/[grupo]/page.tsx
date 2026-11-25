import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GuideShell } from "@/components/guide/guide-shell";
import { groupParams, pageByPath } from "@/lib/guide";

export function generateStaticParams() {
  return groupParams();
}

export async function generateMetadata({ params }: { params: Promise<{ grupo: string }> }): Promise<Metadata> {
  const { grupo } = await params;
  const page = pageByPath(`/guia/${grupo}`);
  return { title: page ? `${page.title} — guia de classes` : "Guia de classes" };
}

export default async function GroupPage({ params }: { params: Promise<{ grupo: string }> }) {
  const { grupo } = await params;
  const page = pageByPath(`/guia/${grupo}`);
  if (!page || page.kind !== "group") notFound();
  return <GuideShell page={page} />;
}
