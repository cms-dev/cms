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

    self.contest_create = $.Callbacks();
    self.contest_update = $.Callbacks();
    self.contest_delete = $.Callbacks();
    self.task_create = $.Callbacks();
    self.task_update = $.Callbacks();
    self.task_delete = $.Callbacks();
    self.team_create = $.Callbacks();
    self.team_update = $.Callbacks();
    self.team_delete = $.Callbacks();
    self.user_create = $.Callbacks();
    self.user_update = $.Callbacks();
    self.user_delete = $.Callbacks();

    self.score_events = $.Callbacks();
    self.rank_events = $.Callbacks();

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
        self.contests[key] = data;

        console.info("Created contest " + key);
        console.debug(data);

        self.contest_create.fire(key, data);
    };

    self.update_contest = function (key, data) {
        var old_data = self.contests[key];

        data["key"] = key;
        self.contests[key] = data;

        console.info("Updated contest " + key);
        console.debug(old_data);
        console.debug(data);

        self.contest_update.fire(key, old_data, data);
    };

    self.delete_contest = function (key) {
        var old_data = self.contests[key];

        delete self.contests[key];

        console.info("Deleted contest " + key);
        console.debug(old_data);

        self.contest_delete.fire(key, old_data);
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
                    self.init_scores();
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
            console.error("Could not find contest " + data["contest"] + " for task " + key);
            return;
        }

        data["key"] = key;
        self.tasks[key] = data;

        console.info("Created task " + key);
        console.debug(data);

        self.task_create.fire(key, data);
    };

    self.update_task = function (key, data) {
        var old_data = self.tasks[key];

        data["key"] = key;
        self.tasks[key] = data;

        console.info("Updated task " + key);
        console.debug(old_data);
        console.debug(data);

        self.task_update.fire(key, old_data, data);
    };

    self.delete_task = function (key) {
        var old_data = self.tasks[key];

        delete self.tasks[key];

        console.info("Deleted task " + key);
        console.debug(old_data);

        self.task_delete.fire(key, old_data);
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

        console.info("Created team " + key);
        console.debug(data);

        self.team_create.fire(key, data);
    };

    self.update_team = function (key, data) {
        var old_data = self.teams[key];

        data["key"] = key;
        self.teams[key] = data;

        console.info("Updated team " + key);
        console.debug(old_data);
        console.debug(data);

        self.team_update.fire(key, old_data, data);
    };

    self.delete_team = function (key) {
        var old_data = self.teams[key];

        delete self.teams[key];

        console.info("Deleted team " + key);
        console.debug(old_data);

        self.team_delete.fire(key, old_data);
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
                    self.init_scores();
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
            console.error("Could not find team " + data["team"] + " for user " + key);
            return;
        }

        data["key"] = key;
        self.users[key] = data;

        console.info("Created user " + key);
        console.debug(data);

        self.user_create.fire(key, data);
    };

    self.update_user = function (key, data) {
        var old_data = self.users[key];

        data["key"] = key;
        self.users[key] = data;

        console.info("Updated user " + key);
        console.debug(old_data);
        console.debug(data);

        self.user_update.fire(key, old_data, data);
    };

    self.delete_user = function (key) {
        var old_data = self.users[key];

        delete self.users[key];

        console.info("Deleted user " + key);
        console.debug(old_data);

        self.user_delete.fire(key, old_data);
    };


    ////// Default scores
    
    self.contest_create.add(function (key, data) {
        // Add scores
        for (var u_id in self.users) {
            self.users[u_id]["c_" + key] = 0.0;
        }
    });

    self.contest_delete.add(function (key, data) {
        // Remove scores
        for (var u_id in self.users) {
            delete self.users[u_id]["c_" + key];
        }
    });

    self.task_create.add(function (key, data) {
        // Add scores
        for (var u_id in self.users) {
            self.users[u_id]["t_" + key] = 0.0;
        }
    });

    /* TODO: When a task is updated we may want to check that all scores are
       still less than or equal to the maximum achievable score.
       Or we may assume that this is handled by the server.
     */

    self.task_delete.add(function (key, data) {
        // Remove scores
        for (var u_id in self.users) {
            /* Actually the next two lines aren't necessary because (in theory)
               the server will delete all submissions and subchanges related to
               this user/task before it deletes the task itself, so the score
               should already have been set to zero. But since this isn't yet
               implemented in the server, we keep this (for now).
             */
            self.users[u_id]["global"] -= self.users[u_id]["t_" + key];
            self.users[u_id]["c_" + data["contest"]] -= self.users[u_id]["t_" + key];
            delete self.users[u_id]["t_" + key];
        }
    });

    self.user_create.add(function (key, data) {
        // Add scores
        for (var t_id in self.tasks) {
            data["t_" + t_id] = 0.0;
        }
        for (var c_id in self.contests) {
            data["c_" + c_id] = 0.0;
        }
        data["global"] = 0.0;
    });

    self.user_update.add(function (key, old_data, data) {
        // Copy scores
        for (var t_id in self.tasks) {
            data["t_" + t_id] = old_data["t_" + t_id];
            delete old_data["t_" + t_id];
        }
        for (var c_id in self.contests) {
            data["c_" + c_id] = old_data["c_" + c_id];
            delete old_data["c_" + c_id];
        }
        data["global"] = old_data["global"];
        delete old_data["global"];
    });

    self.user_delete.add(function (key, old_data) {
        // Remove scores
        for (var t_id in self.tasks) {
            delete old_data["t_" + t_id];
        }
        for (var c_id in self.contests) {
            delete old_data["c_" + c_id];
        }
        delete old_data["global"];
    });


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
                self.init_ranks();
            },
            error: function () {
                console.error("Error while getting the scores");
            }
        });
    };

    self.score_listener = function (event) {
        var data = event.data.split("\n");
        for (var idx in data) {
            var line = data[idx].split(" ");
            self.set_score(line[0], line[1], parseFloat(line[2]));
        }
    };

    self.set_score = function (u_id, t_id, new_score) {
        /* It may be "nice" (if not "useful") to check that the user and task
           do actually exists! It should be the server to ensure that but since
           it doesn't do it (yet) we cannot be sure about that.
         */
        var user = self.users[u_id];
        var old_score = user["t_" + t_id];
        user["global"] += new_score - old_score;
        user["c_" + self.tasks[t_id]["contest"]] += new_score - old_score;
        user["t_" + t_id] = new_score;

        console.info("Changed score for user " + u_id + " and task " + t_id + ": " + old_score + " -> " + new_score);

        self.score_events.fire(u_id, user);
    };

    self.get_score_t = function (u_id, t_id) {
        return self.users[u_id]["t_" + t_id];
    };

    self.get_score_c = function (u_id, c_id) {
        return self.users[u_id]["c_" + c_id];
    };

    self.get_score = function (u_id) {
        return self.users[u_id]["global"];
    };


    ////// Rank

    self.init_ranks = function () {
        var list = new Array();

        for (var u_id in self.users) {
            list.push(self.users[u_id]);
        }

        list.sort(function (a, b) {
            return b["global"] - a["global"];
        });

        var prev_score = null;
        var rank = 0;
        var equal = 1;

        for (var i in list) {
            user = list[i];
            score = user["global"];

            if (score === prev_score) {
                equal += 1;
            } else {
                prev_score = score;
                rank += equal;
                equal = 1;
            }

            user["rank"] = rank;
        }

        self.score_events.add(self.update_rank);

        self.user_create.add(function (u_id, user) {
            var new_rank = 1;

            for (var u_id in self.users) {
                if (self.users[u_id]["global"] > user["global"]) {
                    new_rank += 1;
                }
            }

            user["rank"] = new_rank;
        });

        self.user_update.add(function (u_id, old_user, user) {
            user["rank"] = old_user["rank"];
        });

        /* On deletion:
           The score should already be zero, so the rank should aready be the
           "last" (i.e. the "highest" possible). So deleting that user
           shouldn't cause changes in other users' ranks. But we could add a
           hanlder just to "delete" the rank, in order to return a "clean" user
           object.
         */

        self.init_callback();
    };

    self.update_rank = function (u_id, user) {
        var new_score = user["global"];
        var old_rank = user["rank"];
        var new_rank = 1;

        for (var u2_id in self.users) {
            var user2 = self.users[u2_id];
            if (user2["global"] < new_score && user2["rank"] <= old_rank) {
                user2["rank"] += 1;
                self.rank_events.fire(u2_id, user2);
            } else if (user2["global"] >= new_score && user2["rank"] > old_rank) {
                user2["rank"] -= 1;
                self.rank_events.fire(u2_id, user2);
            }
            if (user2["global"] > new_score) {
                new_rank += 1;
            }
        }

        user["rank"] = new_rank;
        self.rank_events.fire(u_id, user);
    };


    ////// Initialization

    /* The init process works this way:
       - we start init_contests() and init_teams()
       - they each start an asynchronous AJAX request
       - when the requests end their data is processed and then, respectively,
         init_tasks() and init_users() are called
       - they also start an AJAX request and process its data
       - when BOTH requests finished init_scores() is called
       - it does again an AJAX request and process its data
       - at the end it calls init_scores() which calls init_callback()
     */

    self.init = function (callback) {
        self.inits_todo = 2;
        self.init_callback = callback;

        self.init_contests();
        self.init_teams();
    }


    ////// Event listeners

    /* We set the listeners for Server Sent Events.

       This approach presents some issues: some data may be received from these
       listeners (and then processed) while the initial data isn't ready yet.
       This will cause some failures. We don't expect much data to be received
       on the first four listeners, but the fifth (the score listener) is
       supposed to be very active. We may want to change the approach, at least
       on that case, so that we "remember" the data received on these channels
       (without processing it) until the initial data is ready.
     */

    self.es = new EventSource(Config.get_event_url());
    self.es.addEventListener("contest", self.contest_listener);
    self.es.addEventListener("task", self.task_listener);
    self.es.addEventListener("team", self.team_listener);
    self.es.addEventListener("user", self.user_listener);
    self.es.addEventListener("score", self.score_listener);


    ////// Sorted contest and task list

    self.contest_list = new Array();

    self.contest_create.add(function (key, data) {
        data["tasks"] = new Array();

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
    });

    /* TODO: Add also a handler for the "update" event since we have to update
       the contest list in that case too.
     */

    self.contest_delete.add(function (key, data) {
        // Remove data from the sorted contest list
        for (var i = 0; i < self.contest_list.length; i += 1) {
            var b = self.contest_list[i];
            if (key == b["key"]) {
                self.contest_list.splice(i, 1);
                return;
            }
        }
    });

    self.task_create.add(function (key, data) {
        var task_list = self.contests[data["contest"]]["tasks"];

        // Insert data in the sorted task list of the contest
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
    });

    /* TODO: Add also a handler for the "update" event since we have to update
       the task list of the contest in that case too.
     */

    self.task_delete.add(function (key, data) {
        var task_list = self.contests[self.tasks[key]["contest"]]["tasks"];

        // Remove data from the sorted task list of the contest
        for (var i = 0; i < task_list.length; i += 1) {
            var b = task_list[i];
            if (key == b["key"]) {
                task_list.splice(i, 1);
                break;
            }
        }
    });


    ////// Sorted team list

    self.team_list = new Array();

    self.team_create.add(function (key, data) {
        // Insert data in the sorted team list
        var a = data;
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if ((a["name"] < b["name"]) || ((a["name"] < b["name"]) &&
                (key < b["key"]))) {
                // We found the first element which is greater than a
                self.team_list.splice(i, 0, a);
                return;
            }
        }
        self.team_list.push(a);
    });

    /* TODO: Add also a handler for the "update" event since we have to update
       the team list in that case too.
     */

    self.team_delete.add(function (key, data) {
        // Remove data from the sorted team list
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if (key == b["key"]) {
                self.team_list.splice(i, 1);
                break;
            }
        }
    });


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
