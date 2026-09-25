import { providerInfo } from "@/lib/providers";
import { storeDriver } from "@/lib/store";

export async function GET() {
  return Response.json({ ok: true, store: storeDriver(), ...providerInfo() });
}
