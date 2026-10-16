import Image from "next/image";

export default function LoginShowcase() {
  return (
    <aside className="login-showcase" aria-hidden>
      <Image
        src="https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1400&q=80"
        alt=""
        fill
        priority
        className="login-showcase-photo"
      />
      <div className="login-showcase-shade" />
      <div className="login-showcase-content">
        <div className="login-showcase-brand">
          <span>S</span>
          SchoolSarthi
        </div>
        <p className="login-showcase-badge">School portal</p>
        <h2>
          Empowering the
          <br />
          next generation of
          <br />
          leaders.
        </h2>
        <p>
          Streamline administrative tasks, manage student progress, and connect with your faculty all in one secure
          place.
        </p>
      </div>
    </aside>
  );
}
