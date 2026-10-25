import Link from "next/link";

import { uiText } from "@/shared/i18n/ru";

const WORKSPACE_HREF = "/workspace";
const BRAND_LOGO_SRC = "/brand-logo.png";

const TEAM = [
  {
    name: uiText.landingMemberAlexander,
    telegram: "propastin",
    role: uiText.landingTeamLead,
  },
  {
    name: uiText.landingMemberStanislav,
    telegram: "Stasechka1408",
    role: uiText.landingTeamBackend,
  },
  {
    name: uiText.landingMemberNikita,
    telegram: "XCLLNT",
    role: uiText.landingTeamQa,
  },
] as const;

const PATH_STEPS = [
  uiText.landingPath1,
  uiText.landingPath2,
  uiText.landingPath3,
  uiText.landingPath4,
  uiText.landingPath5,
  uiText.landingPath6,
] as const;

const CAPABILITIES = [
  uiText.landingCapScheme,
  uiText.landingCapEditor,
  uiText.landingCapParse,
  uiText.landingCapAnalysis,
  uiText.landingCapLlm,
  uiText.landingCapBehavior,
  uiText.landingCapProject,
  uiText.landingCapAuth,
] as const;

export function LandingPage() {
  return (
    <div className="m3-landing flex min-h-screen min-w-[1280px] flex-col">
      <LandingHeader />
      <main className="flex-1">
        <HeroSection />
        <AboutSection />
        <CapabilitiesSection />
        <ArchitectureSection />
      </main>
      <LandingFooter />
    </div>
  );
}

function LandingHeader() {
  return (
    <header className="m3-top-bar sticky top-0 z-40">
      <div className="m3-shell flex h-16 items-center justify-between gap-6">
        <Link
          href="/"
          className="inline-flex shrink-0 items-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--md-primary)]"
          aria-label={uiText.appName}
          title={uiText.appName}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={BRAND_LOGO_SRC}
            alt={uiText.appName}
            className="h-9 w-auto max-w-[240px] object-contain object-left"
          />
        </Link>

        <nav className="flex items-center gap-1 text-sm" aria-label="Основная навигация">
          <HeaderNavLink href="#about">{uiText.landingNavAbout}</HeaderNavLink>
          <HeaderNavLink href="#capabilities">{uiText.landingNavCapabilities}</HeaderNavLink>
          <HeaderNavLink href="#architecture">{uiText.landingNavArchitecture}</HeaderNavLink>
          <HeaderNavLink href="#team">{uiText.landingNavTeam}</HeaderNavLink>
        </nav>

        <Link href={WORKSPACE_HREF} className="m3-btn-filled shrink-0">
          {uiText.landingCtaMonitor}
        </Link>
      </div>
    </header>
  );
}

function HeaderNavLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} className="m3-nav-link">
      {children}
    </a>
  );
}

function HeroSection() {
  return (
    <section className="m3-shell grid grid-cols-[1.1fr_0.9fr] items-center gap-12 py-20">
      <div className="flex flex-col gap-6">
        <p className="m3-eyebrow">{uiText.appName}</p>
        <h1 className="m3-display">{uiText.landingHeroTitle}</h1>
        <p className="m3-body-lg max-w-xl">{uiText.landingHeroLead}</p>
        <p className="m3-body max-w-xl text-[var(--md-on-surface-variant)]">
          {uiText.landingHeroCase}
        </p>
        <div className="flex items-center gap-3 pt-2">
          <Link href={WORKSPACE_HREF} className="m3-btn-filled">
            {uiText.landingCtaMonitor}
          </Link>
          <a href="#capabilities" className="m3-btn-tonal">
            {uiText.landingCtaSecondary}
          </a>
        </div>
      </div>

      <div className="m3-hero-panel flex min-h-[320px] items-center justify-center p-10">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={BRAND_LOGO_SRC}
          alt=""
          className="h-auto w-full max-w-[440px] object-contain"
        />
      </div>
    </section>
  );
}

function AboutSection() {
  return (
    <section id="about" className="m3-section-band scroll-mt-20">
      <div className="m3-shell grid grid-cols-[1fr_1fr] gap-10 py-16">
        <div className="flex flex-col gap-4">
          <h2 className="m3-title">{uiText.landingAboutTitle}</h2>
          <p className="m3-body">{uiText.landingAboutBody}</p>
        </div>
        <div className="m3-surface-card p-6">
          <h3 className="m3-title-sm mb-4">{uiText.landingPathTitle}</h3>
          <ol className="m3-step-list">
            {PATH_STEPS.map((step, index) => (
              <li key={step}>
                <span className="m3-step-index">{index + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function CapabilitiesSection() {
  return (
    <section id="capabilities" className="m3-shell scroll-mt-20 py-16">
      <div className="mb-8 flex items-end justify-between gap-6">
        <h2 className="m3-title">{uiText.landingCapabilitiesTitle}</h2>
        <Link href={WORKSPACE_HREF} className="m3-btn-filled">
          {uiText.landingCtaMonitor}
        </Link>
      </div>
      <ul className="m3-capability-grid">
        {CAPABILITIES.map((item) => (
          <li key={item} className="m3-surface-card m3-capability-item">
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ArchitectureSection() {
  return (
    <section id="architecture" className="m3-section-band scroll-mt-20">
      <div className="m3-shell grid grid-cols-[1.2fr_0.8fr] gap-10 py-16">
        <div className="flex flex-col gap-4">
          <h2 className="m3-title">{uiText.landingArchTitle}</h2>
          <p className="m3-body">{uiText.landingArchBody}</p>
          <p className="m3-body text-[var(--md-on-surface-variant)]">{uiText.landingArchTruth}</p>
          <div className="m3-surface-card mt-2 p-5">
            <h3 className="m3-title-sm mb-3">{uiText.landingStackTitle}</h3>
            <ul className="m3-plain-list">
              <li>{uiText.landingStackFrontend}</li>
              <li>{uiText.landingStackBackend}</li>
              <li>{uiText.landingStackRuntime}</li>
            </ul>
          </div>
        </div>
        <div className="m3-surface-card p-6">
          <h3 className="m3-title-sm mb-4">{uiText.landingArchLevelsTitle}</h3>
          <ol className="m3-step-list">
            <li>
              <span className="m3-step-index">1</span>
              <span>{uiText.landingArchLevel1}</span>
            </li>
            <li>
              <span className="m3-step-index">2</span>
              <span>{uiText.landingArchLevel2}</span>
            </li>
            <li>
              <span className="m3-step-index">3</span>
              <span>{uiText.landingArchLevel3}</span>
            </li>
          </ol>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  const year = new Date().getFullYear();
  return (
    <footer id="team" className="m3-footer scroll-mt-20">
      <div className="m3-shell grid grid-cols-3 gap-10 py-12">
        <div className="flex flex-col gap-3">
          <Link
            href="/"
            className="inline-flex w-fit items-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--md-primary)]"
            aria-label={uiText.appName}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={BRAND_LOGO_SRC}
              alt={uiText.appName}
              className="h-8 w-auto max-w-[200px] object-contain object-left"
            />
          </Link>
          <p className="m3-body-sm max-w-xs text-[var(--md-on-surface-variant)]">
            {uiText.landingHeroCase}
          </p>
        </div>

        <div>
          <h3 className="m3-footer-heading">{uiText.landingFooterProduct}</h3>
          <ul className="m3-footer-list">
            <li>
              <Link href={WORKSPACE_HREF}>{uiText.landingCtaMonitor}</Link>
            </li>
            <li>
              <a href="#capabilities">{uiText.landingNavCapabilities}</a>
            </li>
            <li>
              <a href="#architecture">{uiText.landingNavArchitecture}</a>
            </li>
            <li>
              <a
                href="https://github.com/tuoot-coding/java-blueprints"
                target="_blank"
                rel="noreferrer"
              >
                {uiText.landingFooterRepo}
              </a>
            </li>
            <li>
              <a href="http://176.124.223.68:8080/" target="_blank" rel="noreferrer">
                {uiText.landingFooterSite}
              </a>
            </li>
          </ul>
        </div>

        <div>
          <h3 className="m3-footer-heading">{uiText.landingFooterTeam}</h3>
          <ul className="m3-footer-team">
            {TEAM.map((member) => (
              <li key={member.telegram}>
                <a
                  href={`https://t.me/${member.telegram}`}
                  target="_blank"
                  rel="noreferrer"
                  className="m3-team-name"
                >
                  {member.name}
                </a>
                <span className="m3-team-role">{member.role}</span>
                <a
                  href={`https://t.me/${member.telegram}`}
                  target="_blank"
                  rel="noreferrer"
                  className="m3-team-tg"
                >
                  @{member.telegram}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="m3-footer-bottom">
        <div className="m3-shell flex items-center justify-between gap-4 py-4 text-sm text-[var(--md-on-surface-variant)]">
          <span>
            © {year} {uiText.appName}. {uiText.landingFooterRights}
          </span>
          <span>{uiText.landingFooterContacts}: Telegram</span>
        </div>
      </div>
    </footer>
  );
}
