import { Suspense } from "react";
import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="container py-5" style={{ maxWidth: 480 }}>
          <p className="text-muted">Loading…</p>
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
