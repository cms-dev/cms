/* Programming contest management system
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

var DataStore = new function () {
    var self = this;

    self.contests = new Object();
    self.tasks = new Object();
    self.teams = new Object();
    self.users = new Object();

    self.scores = new Object();

    self.contest_list = new Array();
    self.team_list = new Array();

    ////// Contest

    self.init_contests = function () {
        $.ajax({
            url: Config.get_contest_list_url(),
            dataType: "json",
            success: function (data) {
                for (var key in data) {
                    self.create_contest(key, data[key]);
                }
                self.init_tasks();
            },
            error: function () {
                console.error("Error while getting the list of contests");
            }
        });
    }

    self.contest_listener = function (event) {
        var cmd = event.data.split(" ");
        if (cmd[0] == "create") {
            $.ajax({
                url: Config.get_contest_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.create_contest(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting contest " + cmd[1]);
                }
            });
        } else if (cmd[0] == "update") {
            $.ajax({
                url: Config.get_contest_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.update_contest(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting contest " + cmd[1]);
                }
            });
        } else if (cmd[0] == "delete") {
            self.delete_contest(cmd[1]);
        }
    };

    self.create_contest = function (key, data) {
        data["key"] = key;
        data["tasks"] = new Array();
        self.contests[key] = data;

        // Insert data in the sorted contest list
        var a = data;
        for (var i = 0; i < self.contest_list.length; i += 1) {
            var b = self.contest_list[i];
            if ((a["begin"] < b["begin"]) || ((a["begin"] == b["begin"]) &&
               ((a["end"]   < b["end"]  ) || ((a["end"]   == b["end"]  ) &&
               ((a["name"]  < b["name"] ) || ((a["name"]  == b["name"] ) &&
               (key < b["key"]))))))) {
                // We found the first element which is greater than a
                self.contest_list.splice(i, 0, a);
                return;
            }
        }
        self.contest_list.push(a);
    };

    self.update_contest = function (key, data) {
        self.delete_contest(key);
        self.create_contest(key, data);
    };

    self.delete_contest = function (key) {
        delete self.contests[key];

        // Remove data from the sorted contest list
        for (var i = 0; i < self.contest_list.length; i += 1) {
            var b = self.contest_list[i];
            if (key == b["key"]) {
                self.contest_list.splice(i, 1);
                return;
            }
        }
        self.contest_list.pop();
    };


    ////// Task

    self.init_tasks = function () {
        $.ajax({
            url: Config.get_task_list_url(),
            dataType: "json",
            success: function (data) {
                for (var key in data) {
                    self.create_task(key, data[key]);
                }
                self.inits_todo -= 1;
                if (self.inits_todo == 0) {
                    self.init_callback();
                }
            },
            error: function () {
                console.error("Error while getting the list of tasks");
            }
        });
    }

    self.task_listener = function (event) {
        var cmd = event.data.split(" ");
        if (cmd[0] == "create") {
            $.ajax({
                url: Config.get_task_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.create_task(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting task " + cmd[1]);
                }
            });
        } else if (cmd[0] == "update") {
            $.ajax({
                url: Config.get_task_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.update_task(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting task " + cmd[1]);
                }
            });
        } else if (cmd[0] == "delete") {
            self.delete_task(cmd[1]);
        }
    };

    self.create_task = function (key, data) {
        if (self.contests[data["contest"]] === undefined)
        {
            console.error("Could not find contest: " + data["contest"]);
            return;
        }
        var task_list = self.contests[data["contest"]]["tasks"];

        data["key"] = key;
        self.tasks[key] = data;

        // Insert data in the sorted task list for the contest
        var a = data;
        for (var i = 0; i < task_list.length; i += 1) {
            var b = task_list[i];
            if ((a["order"] < b["order"]) || ((a["order"] == b["order"]) &&
               ((a["name"]  < b["name"] ) || ((a["name"]  == b["name"] ) &&
               (key < b["key"]))))) {
                // We found the first element which is greater than a
                task_list.splice(i, 0, a);
                return;
            }
        }
        task_list.push(a);
    };


    self.update_task = function (key, data) {
        self.delete_task(key);
        self.create_task(key, data);
    };

    self.delete_task = function (key, data) {
        var task_list = self.contests[self.tasks[key]["contest"]]["tasks"];

        delete self.tasks[key];

        // Remove data from the sorted task list for the contest
        for (var i = 0; i < task_list.length; i += 1) {
            var b = task_list[i];
            if (key == b["key"]) {
                task_list.splice(i, 1);
                return;
            }
        }
        task_list.pop();
    };


    ////// Team

    self.init_teams = function () {
        $.ajax({
            url: Config.get_team_list_url(),
            dataType: "json",
            success: function (data) {
                for (var key in data) {
                    self.create_team(key, data[key]);
                }
                self.init_users();
            },
            error: function () {
                console.error("Error while getting the list of teams");
            }
        });
    }

    self.team_listener = function (event) {
        var cmd = event.data.split(" ");
        if (cmd[0] == "create") {
            $.ajax({
                url: Config.get_team_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.create_team(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting team " + cmd[1]);
                }
            });
        } else if (cmd[0] == "update") {
            $.ajax({
                url: Config.get_team_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.update_team(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting team " + cmd[1]);
                }
            });
        } else if (cmd[0] == "delete") {
            self.delete_team(cmd[1]);
        }
    };

    self.create_team = function (key, data) {
        data["key"] = key;
        self.teams[key] = data;

        // Insert data in the sorted team list
        var a = data;
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if ((a["name"] < b["name"]) || (key < b["key"])) {
                // We found the first element which is greater than a
                self.team_list.splice(i, 0, a);
                return;
            }
        }
        self.team_list.push(a);
    };

    self.update_team = function (key, data) {
        self.delete_team(key);
        self.create_team(key, data);
    };

    self.delete_team = function (key, data) {
        delete self.teams[key];

        // Remove data from the sorted team list
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if (key == b["key"]) {
                self.team_list.splice(i, 1);
                return;
            }
        }
        self.team_list.pop();
    };


    ////// User

    self.init_users = function () {
        $.ajax({
            url: Config.get_user_list_url(),
            dataType: "json",
            success: function (data) {
                for (var key in data) {
                    self.create_user(key, data[key]);
                }
                self.inits_todo -= 1;
                if (self.inits_todo == 0) {
                    self.init_callback();
                }
            },
            error: function () {
                console.error("Error while getting the list of users");
            }
        });
    }

    self.user_listener = function (event) {
        var cmd = event.data.split(" ");
        if (cmd[0] == "create") {
            $.ajax({
                url: Config.get_user_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.create_user(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting user " + cmd[1]);
                }
            });
        } else if (cmd[0] == "update") {
            $.ajax({
                url: Config.get_user_read_url(cmd[1]),
                dataType: "json",
                success: function (data) {
                    self.update_user(cmd[1], data);
                },
                error: function () {
                    console.error("Error while getting user " + cmd[1]);
                }
            });
        } else if (cmd[0] == "delete") {
            self.delete_user(cmd[1]);
        }
    };

    self.create_user = function (key, data) {
        if (data["team"] !== null && self.teams[data["team"]] === undefined)
        {
            console.error("Could not find team: " + data["team"]);
            data["team"] = null;
        }

        data["key"] = key;
        self.users[key] = data;
    };

    self.update_user = function (key, data) {
        self.delete_user(key);
        self.create_user(key, data);
    };

    self.delete_user = function (key) {
        delete self.users[key];
    };


    ////// Score

    self.init_scores = function () {
        $.ajax({
            url: Config.get_score_url(),
            success: function (data) {
                data = data.split("\n");
                for (var idx = 0; idx < data.length - 1; idx += 1) {
                    var line = data[idx].split(" ");
                    self.set_score(line[0], line[1], parseFloat(line[2]));
                }
                self.inits_todo -= 1;
                if (self.inits_todo == 0) {
                    self.init_callback();
                }
            },
            error: function () {
                console.error("Error while getting the scores");
            }
        });
    }

    self.score_listener = function (event) {
        console.debug(event.data);
        var data = event.data.split("\n");
        for (var idx in data) {
            console.debug(data[idx]);
            if (data[idx] == "")
                console.error("GOT AN EMPTY LINE!!!")
            var line = data[idx].split(" ");
            self.set_score(line[0], line[1], parseFloat(line[2]));
        }
    };

    self.set_score = function (user, task, score) {
        if (score === 0.0) {
            delete self.scores[user][task];
            if (Object.keys(self.scores[user]).length === 0) {
                delete self.scores[user];
            }
        } else {
            if (!self.scores[user]) {
                self.scores[user] = new Object();
            }
            self.scores[user][task] = score;
        }
    };

    self.get_score_t = function (user, task) {
        if (!self.scores[user] || !self.scores[user][task]) {
            return 0.0;
        } else {
            return self.scores[user][task];
        }
    };

    self.get_score_c = function (user, contest) {
        if (!self.scores[user]) {
            return 0.0;
        } else {
            var sum = 0.0;
            for (var t_id in self.scores[user]) {
                if (self.tasks[t_id]["contest"] == contest) {
                    sum += self.scores[user][t_id];
                }
            }
            return sum;
        }
    };

    self.get_score = function (user) {
        if (!self.scores[user]) {
            return 0.0;
        } else {
            var sum = 0.0;
            for (var t_id in self.scores[user]) {
                sum += self.scores[user][t_id];
            }
            return sum;
        }
    };


    ////// Initialization
    self.init = function (callback) {
        self.inits_todo = 3;
        self.init_callback = callback;

        self.init_contests();
        self.init_teams();
        self.init_scores();
    }

    ////// Event listeners
    self.es = new EventSource(Config.get_event_url());
    self.es.addEventListener("contest", self.contest_listener);
    self.es.addEventListener("task", self.task_listener);
    self.es.addEventListener("team", self.team_listener);
    self.es.addEventListener("user", self.user_listener);


    self.set_selected = function (u_id, flag) {};
    self.get_selected = function (u_id) {return false;};

    ////// Selection

    self.select_handlers = new Array();

    self.set_selected = function (u_id, flag) {
        if (self.users[u_id]["selected"] != flag) {
            self.users[u_id]["selected"] = flag;
            for (var idx in self.select_handlers) {
                self.select_handlers[idx](u_id, flag);
            }
        }
    };

    self.get_selected = function (u_id) {
        return self.users[u_id]["selected"];
    };

    self.add_select_handler = function (handler) {
        self.select_handlers.push(handler);
    };
};
