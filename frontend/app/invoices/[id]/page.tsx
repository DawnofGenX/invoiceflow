import InvoiceDetail from "@/components/InvoiceDetail";

export const instant = false;

export default async function InvoiceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <InvoiceDetail id={id} />;
}
