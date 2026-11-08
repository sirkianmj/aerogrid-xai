import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { RelayTopologyEditor, parseRelayChain } from "./RelayTopologyEditor"

describe("parseRelayChain", () => {
  it("blank input → null chain", () => {
    expect(parseRelayChain("", 5)).toEqual({ chain: null, error: null })
    expect(parseRelayChain("   ", 5)).toEqual({ chain: null, error: null })
  })

  it("valid comma-separated → chain array", () => {
    expect(parseRelayChain("0,1,2", 5)).toEqual({ chain: [0, 1, 2], error: null })
    expect(parseRelayChain("  2 , 0 ", 5)).toEqual({ chain: [2, 0], error: null })
  })

  it("out-of-range id → error", () => {
    const r = parseRelayChain("0,7", 5)
    expect(r.chain).toBeNull()
    expect(r.error).toMatch(/not in \[0, 5\)/)
  })

  it("duplicate id → error", () => {
    const r = parseRelayChain("0,1,0", 5)
    expect(r.chain).toBeNull()
    expect(r.error).toMatch(/appears twice/)
  })

  it("non-integer → error", () => {
    const r = parseRelayChain("0,abc", 5)
    expect(r.chain).toBeNull()
    expect(r.error).toMatch(/not an integer/)
  })
})

describe("RelayTopologyEditor", () => {
  const onChange = vi.fn()

  beforeEach(() => {
    onChange.mockReset()
  })

  it("renders input and forward fraction field", () => {
    render(
      <RelayTopologyEditor
        nUavs={5}
        relayTopology={null}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    expect(screen.getByLabelText("Relay chain UAV IDs")).toBeInTheDocument()
    expect(screen.getByLabelText("Relay forward fraction")).toBeInTheDocument()
  })

  it("shows warning when nUavs < 2", () => {
    render(
      <RelayTopologyEditor
        nUavs={1}
        relayTopology={null}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    expect(screen.getByTestId("relay-editor-too-few-uavs")).toBeInTheDocument()
  })

  it("valid chain triggers onChange with array", async () => {
    const user = userEvent.setup()
    render(
      <RelayTopologyEditor
        nUavs={5}
        relayTopology={null}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText("Relay chain UAV IDs")
    await user.type(input, "0,1,2")
    // Last call should have relay_topology: [0,1,2]
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(lastCall.relay_topology).toEqual([0, 1, 2])
  })

  it("invalid id shows error and does not call onChange", async () => {
    const user = userEvent.setup()
    render(
      <RelayTopologyEditor
        nUavs={3}
        relayTopology={null}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText("Relay chain UAV IDs")
    await user.type(input, "0,5")
    expect(screen.getByTestId("relay-editor-error")).toBeInTheDocument()
    // onChange should not have been called with invalid data
    for (const [patch] of onChange.mock.calls) {
      if ("relay_topology" in patch && patch.relay_topology !== null) {
        for (const id of patch.relay_topology) {
          expect(id).toBeLessThan(3)
        }
      }
    }
  })

  it("shows chain preview when valid", () => {
    render(
      <RelayTopologyEditor
        nUavs={5}
        relayTopology={[0, 1, 2]}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    const preview = screen.getByTestId("relay-editor-chain")
    expect(preview.textContent).toMatch(/UAV-0/)
    expect(preview.textContent).toMatch(/UAV-2/)
  })

  it("forward fraction change triggers onChange", async () => {
    const user = userEvent.setup()
    render(
      <RelayTopologyEditor
        nUavs={5}
        relayTopology={[0, 1]}
        relayFraction={0.7}
        onChange={onChange}
      />,
    )
    const fracInput = screen.getByLabelText("Relay forward fraction")
    await user.clear(fracInput)
    await user.type(fracInput, "0.85")
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(lastCall.relay_fraction).toBeDefined()
  })
})
