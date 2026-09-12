import LeadPage from '@/components/LeadPage';

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LeadPage id={id} />;
}
