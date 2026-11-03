import { render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useHandleKeyDown, type KeyMap } from "./useHandleKeyDown";

function Harness({ keyMap, enabled }: { keyMap: KeyMap; enabled?: boolean }) {
  useHandleKeyDown(keyMap, { enabled });
  return (
    <>
      <input aria-label="Value" />
      <div contentEditable aria-label="Notes" role="textbox" />
    </>
  );
}

describe("useHandleKeyDown", () => {
  it("calls the handler of the pressed key, anywhere on the page", async () => {
    const down = vi.fn();
    const up = vi.fn();
    const user = userEvent.setup();
    renderHook(() => useHandleKeyDown({ ArrowDown: down, ArrowUp: up }));

    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowUp}");

    expect(down).toHaveBeenCalledTimes(2);
    expect(up).toHaveBeenCalledTimes(1);
  });

  it("matches letters whatever their case, and named keys", async () => {
    const next = vi.fn();
    const confirm = vi.fn();
    const user = userEvent.setup();
    renderHook(() => useHandleKeyDown({ j: next, Enter: confirm }));

    await user.keyboard("j{Shift>}J{/Shift}{Enter}");

    expect(next).toHaveBeenCalledTimes(2);
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("prevents the browser default for handled keys only", async () => {
    const user = userEvent.setup();
    const events: KeyboardEvent[] = [];
    const record = (event: KeyboardEvent) => events.push(event);
    window.addEventListener("keydown", record);
    renderHook(() => useHandleKeyDown({ ArrowDown: () => {} }));

    await user.keyboard("{ArrowDown}{ArrowUp}");
    window.removeEventListener("keydown", record);

    expect(events.map((e) => [e.key, e.defaultPrevented])).toEqual([
      ["ArrowDown", true],
      ["ArrowUp", false],
    ]);
  });

  it("leaves plain keys to the field I am typing in", async () => {
    const next = vi.fn();
    const user = userEvent.setup();
    render(<Harness keyMap={{ j: next, ArrowDown: next }} />);

    await user.type(screen.getByLabelText("Value"), "jj{ArrowDown}");
    await user.type(screen.getByRole("textbox", { name: "Notes" }), "j");

    expect(next).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Value")).toHaveValue("jj");
  });

  it("still runs shortcuts with a modifier while I type, e.g. Mod+Enter to save", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    render(<Harness keyMap={{ "Mod+Enter": save }} />);
    await user.click(screen.getByLabelText("Value"));

    // jsdom is not a Mac, so Mod is Control
    await user.keyboard("{Enter}{Control>}{Enter}{/Control}{Meta>}{Enter}{/Meta}");

    expect(save).toHaveBeenCalledTimes(1);
  });

  it("requires the exact modifiers of a combo", async () => {
    const back = vi.fn();
    const user = userEvent.setup();
    renderHook(() => useHandleKeyDown({ "Shift+Tab": back }));

    await user.keyboard("{Tab}{Shift>}{Tab}{/Shift}");

    expect(back).toHaveBeenCalledTimes(1);
  });

  it("does nothing while disabled, and uses the latest handlers", async () => {
    const first = vi.fn();
    const second = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<Harness keyMap={{ k: first }} enabled={false} />);

    await user.keyboard("k");
    rerender(<Harness keyMap={{ k: second }} />);
    await user.keyboard("k");

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("stops listening when the component unmounts", async () => {
    const handler = vi.fn();
    const user = userEvent.setup();
    const { unmount } = renderHook(() => useHandleKeyDown({ Escape: handler }));

    unmount();
    await user.keyboard("{Escape}");

    expect(handler).not.toHaveBeenCalled();
  });
});
