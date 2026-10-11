import { Suspense } from "react";
import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="login-split">
          <section className="login-panel">
            <p className="muted">Loading…</p>
          </section>
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
