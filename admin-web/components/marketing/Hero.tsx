import Image from "next/image";
import Link from "next/link";

export default function Hero() {
  return (
    <section className="site-hero" id="home">
      <div className="reveal">
        <p className="site-kicker">Smart school management platform</p>
        <h1>
          Everything your school needs,
          <br />
          in one powerful platform
        </h1>
        <p className="site-hero-copy">
          Manage students, teachers, attendance, academics, fees, communication, and
          school operations from one centralized console built for clarity.
        </p>
        <div className="site-cta-row">
          <Link href="/login" className="btn-pill btn-pill-green">
            Get started
          </Link>
          <Link href="/login" className="btn-pill btn-pill-green-soft">
            Request demo
          </Link>
        </div>
      </div>

      <div className="site-hero-visual reveal">
        <div className="site-wave" aria-hidden />
        <div className="site-dots" aria-hidden />
        <div className="site-arrow" aria-hidden />

        <div className="site-float-card left">
          <span className="stars" aria-hidden>
            ★★★
          </span>
          Top rated support
        </div>
        <div className="site-float-card right">
          14+ operational modules for a smoother academic experience.
        </div>
        <div className="site-float-card metric">
          <strong>98%</strong>
          <span>Attendance insights</span>
        </div>

        <div className="site-hero-frame">
          <Image
            src="https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1000&q=80"
            alt="Students collaborating on school work with a laptop"
            width={1000}
            height={1250}
            priority
          />
          <div className="site-mock-card" aria-hidden>
            <div className="site-mock-bar" />
            <div className="site-mock-row" />
            <div className="site-mock-row short" />
            <div className="site-mock-chips">
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
