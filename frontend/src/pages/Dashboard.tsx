import { Candidates } from "../components/Candidates";
import { MoversBoard } from "../components/MoverCard";
import { NewsFeed } from "../components/NewsFeed";

export function Dashboard() {
  return (
    <div className="space-y-4">
      <MoversBoard />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Candidates />
        </div>
        <div>
          <NewsFeed />
        </div>
      </div>
    </div>
  );
}
