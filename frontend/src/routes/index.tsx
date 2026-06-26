import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export default function Home() {
  const { data, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.get("/api/v1/health").then((r) => r.data),
  });

  if (isLoading) return <div className="flex h-screen items-center justify-center">Loading...</div>;

  return (
    <main className="flex h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-bold">funding_backtester</h1>
      <p className="text-muted-foreground">API Status: {data?.status}</p>
    </main>
  );
}