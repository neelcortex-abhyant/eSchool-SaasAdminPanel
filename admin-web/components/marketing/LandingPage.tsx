"use client";

import SiteNavbar from "@/components/marketing/SiteNavbar";
import Hero from "@/components/marketing/Hero";
import SiteFooter from "@/components/marketing/SiteFooter";
import {
  ContactSection,
  CTASection,
  FAQSection,
  FeaturesSection,
  HowItWorksSection,
  PricingSection,
  RolesSection,
  ShowcaseSection,
  StatsSection,
  TestimonialsSection,
  WhyChooseSection,
} from "@/components/marketing/SiteSections";

export default function LandingPage() {
  return (
    <div className="site">
      <SiteNavbar />
      <main>
        <Hero />
        <StatsSection />
        <FeaturesSection />
        <ShowcaseSection />
        <RolesSection />
        <HowItWorksSection />
        <WhyChooseSection />
        <PricingSection />
        <TestimonialsSection />
        <FAQSection />
        <CTASection />
        <ContactSection />
      </main>
      <SiteFooter />
    </div>
  );
}
