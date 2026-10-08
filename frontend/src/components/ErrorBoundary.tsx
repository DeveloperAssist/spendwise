import { Component, type ErrorInfo, type ReactNode } from "react";

// If any page throws while rendering, show a way out instead of a blank white screen.
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("SpendWise crashed:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="grid min-h-screen place-items-center p-6 text-center">
        <div>
          <h1 className="text-xl font-bold">Something went wrong</h1>
          <p className="mt-2 text-sm text-slate-500">{this.state.error.message}</p>
          <button className="btn mt-5" onClick={() => location.reload()}>Reload SpendWise</button>
        </div>
      </div>
    );
  }
}
