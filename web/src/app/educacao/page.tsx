import type { Metadata } from "next";
import { EducationHub } from "@/components/education/hub";
import { StudyPage } from "@/components/education/study-parts";

export const metadata: Metadata = {
  title: "Modo educação — triagem de classe esportiva",
  description: "Casos fictícios para estudar a triagem de classe esportiva no atletismo paralímpico, com o rastro dos critérios.",
};

export default function EducacaoPage() {
  return (
    <StudyPage
      title="Modo educação"
      intro="Pratique com casos fictícios: você escolhe a classe, e depois vê a resposta com o rastro dos critérios, passo a passo."
    >
      <EducationHub />
    </StudyPage>
  );
}
