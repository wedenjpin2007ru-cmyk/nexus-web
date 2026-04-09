import { redirect } from "next/navigation";
import { isAdminRequest } from "@/app/lib/auth";
import AdminPanel from "./panel";

export default async function AdminPage() {
  const ok = await isAdminRequest();
  if (!ok) redirect("/admin/login");

  return (
    <AdminPanel />
  );
}

