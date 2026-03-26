import { ClaimDetailPage } from "@/components/claim-detail-page";

export function generateStaticParams() {
  return Array.from({ length: 12 }, (_, index) => ({
    id: String(index + 1),
  }));
}

export default function ClaimDetailRoute({ params }: { params: { id: string } }) {
  return <ClaimDetailPage claimId={params.id} />;
}
