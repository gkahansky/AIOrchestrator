import { useState } from "react"
import { useMutation } from "@tanstack/react-query"

const BASE = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"

export function getHeaders(): HeadersInit {
  const token = localStorage.getItem("api_token") ?? "test"
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}: ${res.statusText}`
    try {
      const body = await res.json()
      message = body.detail ?? message
    } catch {}
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

interface GigPackage {
  name: string
  price: number
  delivery_days: number
  revisions: number
  description: string
  features: string[]
}

interface GigFaq {
  question: string
  answer: string
}

interface GigRequirement {
  requirement: string
  is_mandatory: boolean
  type: string
}

interface GigResponse {
  category: string
  subcategory: string
  service_type: string
  gig_metadata: Record<string, string>
  gig_title: string
  gig_description: string
  packages: GigPackage[]
  faq: GigFaq[]
  requirements: GigRequirement[]
  tags: string[]
  image_url: string | null
  image_error: string | null
  output_path: string
}

async function generateGig(platform: string, venture: string): Promise<GigResponse> {
  const res = await fetch(`${BASE}/api/platform/gigs/generate`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ platform, venture }),
  })
  return handleResponse<GigResponse>(res)
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
        copied ? "bg-green-100 text-green-800" : "bg-surface-variant text-on-surface-variant hover:bg-primary hover:text-on-primary"
      }`}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  )
}

export default function GigGenerator() {
  const [platform, setPlatform] = useState("Fiverr")
  const [venture, setVenture] = useState("podcast_notes")

  const mutation = useMutation({
    mutationFn: () => generateGig(platform, venture),
  })

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black font-headline tracking-tight text-on-surface mb-1">
            Gig Generator
          </h1>
          <p className="text-sm text-on-surface-variant">
            Generate highly-converting storefront listings for any platform.
          </p>
        </div>
      </div>

      <div className="card p-6 flex items-end gap-4">
        <div className="flex-1">
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-2">
            Platform
          </label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          >
            <option value="Fiverr">Fiverr</option>
            <option value="Upwork" disabled>Upwork (Coming soon)</option>
          </select>
        </div>

        <div className="flex-1">
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-2">
            Venture Service
          </label>
          <select
            value={venture}
            onChange={(e) => setVenture(e.target.value)}
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          >
            <option value="podcast_notes">EchoForge: Podcast Notes & Content</option>
            <option value="marketing_audit">EchoForge: Marketing Audit</option>
          </select>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="btn-primary py-2 px-6 shadow-sm"
        >
          {mutation.isPending ? "Generating..." : "Generate Assets"}
        </button>
      </div>

      {mutation.isError && (
        <div className="bg-error/10 text-error p-4 rounded-xl text-sm font-medium">
          Failed to generate gig: {mutation.error.message}
        </div>
      )}

      {mutation.isSuccess && mutation.data && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold font-headline">Generated Assets</h2>
            <a
              href="https://www.fiverr.com/cp/gigs/new" // Generic new gig URL
              target="_blank"
              rel="noreferrer"
              className="btn bg-primary text-on-primary px-4 py-2 hover:bg-primary-dark transition-colors"
            >
              Upload to {platform} <span className="material-symbols-outlined text-[18px] ml-1">open_in_new</span>
            </a>
          </div>

          <div className="card p-6 space-y-8">
            {/* Title & Tags */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant">Classification</h3>
                </div>
                <div className="p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20 font-medium text-sm space-y-2">
                  <div className="flex justify-between items-center border-b border-outline-variant/10 pb-2">
                    <span className="text-on-surface-variant">Category:</span>
                    <div className="flex items-center gap-2">
                      <span>{mutation.data.category} &gt; {mutation.data.subcategory}</span>
                      <CopyButton text={`${mutation.data.category} > ${mutation.data.subcategory}`} />
                    </div>
                  </div>
                  <div className="flex justify-between items-center border-b border-outline-variant/10 pb-2">
                    <span className="text-on-surface-variant">Service Type:</span>
                    <div className="flex items-center gap-2">
                      <span>{mutation.data.service_type}</span>
                      <CopyButton text={mutation.data.service_type} />
                    </div>
                  </div>
                  <div className="pt-2 flex flex-col gap-1">
                    <span className="text-on-surface-variant mb-1">Gig Metadata:</span>
                    {Object.entries(mutation.data.gig_metadata || {}).map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center text-xs">
                        <span className="font-bold">{k}:</span>
                        <div className="flex items-center gap-2">
                          <span>{v}</span>
                          <CopyButton text={v} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant">Gig Title</h3>
                  <CopyButton text={mutation.data.gig_title} />
                </div>
                <div className="p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20 font-medium font-serif text-lg">
                  {mutation.data.gig_title}
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <div className="flex justify-between items-center">
                  <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant">Search Tags</h3>
                  <CopyButton text={mutation.data.tags.join(", ")} />
                </div>
                <div className="flex flex-wrap gap-2 p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
                  {mutation.data.tags.map(tag => (
                    <span key={tag} className="px-3 py-1 bg-primary/10 text-primary font-medium text-sm rounded-full">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <hr className="border-outline-variant/20" />

            {/* Description */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant">Description</h3>
                <CopyButton text={mutation.data.gig_description} />
              </div>
              <div className="p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20 prose max-w-none text-sm whitespace-pre-wrap">
                {mutation.data.gig_description}
              </div>
            </div>

            <hr className="border-outline-variant/20" />

            {/* Packages */}
            <div>
              <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant mb-4">Pricing Packages</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {mutation.data.packages.map((pkg, i) => (
                  <div key={i} className="border border-outline-variant/30 rounded-xl p-5 bg-surface-container-lowest">
                    <div className="flex flex-col gap-4 mb-4">
                      <div className="flex justify-between items-start gap-2">
                        <div>
                          <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block mb-1">Name (Max 35)</span>
                          <h4 className="font-bold text-sm">{pkg.name}</h4>
                        </div>
                        <CopyButton text={pkg.name} />
                      </div>
                      
                      <div className="flex justify-between items-start gap-2">
                        <div>
                          <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block mb-1">Description (Max 100)</span>
                          <p className="text-sm text-on-surface-variant">{pkg.description}</p>
                        </div>
                        <CopyButton text={pkg.description} />
                      </div>
                      
                      <div className="flex justify-between items-start gap-2">
                        <div>
                          <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block mb-1">Custom Features (If applicable)</span>
                          <ul className="space-y-1 mt-1">
                            {pkg.features.map((f, j) => (
                              <li key={j} className="text-sm text-on-surface-variant leading-snug">• {f}</li>
                            ))}
                          </ul>
                        </div>
                        <CopyButton text={pkg.features.join("\n")} />
                      </div>
                    </div>
                    
                    <div className="flex justify-between items-end mt-4 pt-4 border-t border-outline-variant/30">
                      <div className="text-2xl font-black">${pkg.price}</div>
                      <div className="flex items-center gap-4 text-xs font-medium text-on-surface-variant">
                        <div className="flex items-center gap-1"><span className="material-symbols-outlined text-[16px]">schedule</span> {pkg.delivery_days} Days</div>
                        <div className="flex items-center gap-1"><span className="material-symbols-outlined text-[16px]">autorenew</span> {pkg.revisions} Revs</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <hr className="border-outline-variant/20" />

            {/* FAQ */}
            <div className="space-y-2">
              <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant mb-4">Frequently Asked Questions</h3>
              <div className="space-y-4">
                {mutation.data.faq.map((faq, i) => (
                  <div key={i} className="flex flex-col gap-3 p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block mb-1">Question</span>
                        <h4 className="font-bold text-sm">{faq.question}</h4>
                      </div>
                      <CopyButton text={faq.question} />
                    </div>
                    <hr className="border-outline-variant/10" />
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider block mb-1">Answer</span>
                        <p className="text-sm text-on-surface-variant">{faq.answer}</p>
                      </div>
                      <CopyButton text={faq.answer} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <hr className="border-outline-variant/20" />

            {/* Requirements */}
            <div className="space-y-2">
              <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant mb-4">Buyer Requirements</h3>
              <div className="space-y-4">
                {mutation.data.requirements?.map((req, i) => (
                  <div key={i} className="flex justify-between items-start gap-4 p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">{req.type}</span>
                        {req.is_mandatory && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-error/10 text-error">MANDATORY</span>}
                      </div>
                      <p className="text-sm font-medium text-on-surface">{req.requirement}</p>
                    </div>
                    <CopyButton text={req.requirement} />
                  </div>
                ))}
              </div>
            </div>

            <hr className="border-outline-variant/20" />

            {/* Cover Image */}
            <div className="space-y-4">
              <h3 className="text-sm font-label font-bold uppercase text-on-surface-variant">Gig Cover Image</h3>
              {mutation.data.image_url ? (
                <div className="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
                  <div className="h-24 w-40 bg-surface-variant rounded flex items-center justify-center overflow-hidden">
                    <span className="material-symbols-outlined text-4xl text-on-surface-variant/50">image</span>
                  </div>
                  <div>
                    <h4 className="font-bold text-sm mb-1">Generated 16:9 Cover Thumbnail</h4>
                    <p className="text-sm text-on-surface-variant mb-3">Stored safely in Google Drive.</p>
                    <a 
                      href={mutation.data.image_url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="text-primary font-medium text-sm flex items-center gap-1 hover:underline"
                    >
                      <span className="material-symbols-outlined text-[16px]">download</span>
                      Download from Drive
                    </a>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-error/10 text-error rounded-lg text-sm font-medium">
                  Cover Image generation skipped or failed.{mutation.data.image_error ? ` Error: ${mutation.data.image_error}` : ""}
                </div>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  )
}