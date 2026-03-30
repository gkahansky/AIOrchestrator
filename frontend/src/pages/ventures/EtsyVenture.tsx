export default function EtsyVenture() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="material-symbols-outlined text-[24px] text-outline">storefront</span>
          <h1 className="font-headline font-bold text-2xl text-on-surface">
            MiroPrintStudio — Etsy
          </h1>
        </div>
        <p className="text-sm font-body text-on-surface-variant">
          AI-generated digital wall art shop
        </p>
      </div>

      {/* Coming Soon card */}
      <div className="bg-surface-container-lowest rounded-2xl shadow-float px-10 py-16 text-center max-w-lg">
        <div className="w-16 h-16 rounded-2xl bg-surface-container-high flex items-center justify-center mx-auto mb-5">
          <span className="material-symbols-outlined text-[32px] text-on-surface-variant">
            construction
          </span>
        </div>
        <h2 className="font-headline font-bold text-xl text-on-surface mb-2">
          Pipeline Coming Soon
        </h2>
        <p className="text-sm font-body text-on-surface-variant leading-relaxed">
          The Etsy venture pipeline is under active development. Image generation, listing
          management, and automated fulfillment will be available here once the pipeline is ready.
        </p>
        <div className="mt-6 flex items-center justify-center gap-2 text-xs font-label text-on-surface-variant">
          <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
          In development — EchoForge Sprint backlog
        </div>
      </div>
    </div>
  )
}
