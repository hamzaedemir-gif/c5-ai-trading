import { MoversBoard } from "../components/MoverCard";
import { NewsFeed } from "../components/NewsFeed";
import { OpportunityFeed } from "../components/OpportunityFeed";

export function Dashboard() {
  return (
    <div className="space-y-4">
      <OpportunityFeed />
      <MoversBoard />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 text-mute text-xs italic">
          Tap any opportunity card above for the full chart, signal breakdown
          and audit log. Use <span className="text-accent">Paper Buy</span> to
          add a simulated position sized by the risk module.
        </div>
        <div>
          <NewsFeed />
        </div>
      </div>
    </div>
  );
}
